using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Continuum;

public sealed class Engine : IDisposable
{
    Process? process;
    IntPtr job;
    public int Port { get; private set; }
    public bool Running => process is { HasExited: false };
    public static string Binary => Path.Combine(AppContext.BaseDirectory, "engine", "xray.exe");
    public async Task StartAsync(Profile profile, bool tun, int mtu, CancellationToken ct)
    {
        Stop();
        if (!File.Exists(Binary) || (tun && !File.Exists(Path.Combine(Path.GetDirectoryName(Binary)!, "wintun.dll"))))
            throw new InvalidOperationException("Engine files missing. Extract the complete Continuum ZIP before opening the app.");
        using (var listener = new TcpListener(IPAddress.Loopback, 0))
        { listener.Start(); Port = ((IPEndPoint)listener.LocalEndpoint).Port; }
        job = Native.CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new InvalidOperationException("Could not create engine lifecycle guard.");
        var limits = new Native.Limits(); limits.Basic.LimitFlags = 0x2000; // KILL_ON_JOB_CLOSE
        if (!Native.SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf<Native.Limits>()))
        { Dispose(); throw new InvalidOperationException("Could not configure engine lifecycle guard."); }
        var start = new ProcessStartInfo(Binary) { UseShellExecute = false, CreateNoWindow = false,
            WindowStyle = ProcessWindowStyle.Hidden, RedirectStandardInput = true, RedirectStandardOutput = true,
            RedirectStandardError = true, WorkingDirectory = Path.GetDirectoryName(Binary)! };
        start.ArgumentList.Add("run"); start.ArgumentList.Add("-config"); start.ArgumentList.Add("stdin:");
        process = new Process { StartInfo = start };
        try
        {
            process.Start();
            if (!Native.AssignProcessToJobObject(job, process.Handle)) throw new InvalidOperationException("Engine lifecycle guard failed.");
            // Drain but never retain or expose raw engine messages (may contain secrets).
            process.OutputDataReceived += (_, _) => { }; process.ErrorDataReceived += (_, _) => { };
            process.BeginOutputReadLine(); process.BeginErrorReadLine();
            await process.StandardInput.WriteAsync(profile.Config(tun, Port, mtu).ToJsonString().AsMemory(), ct);
            process.StandardInput.Close();
            for (int i = 0; i < 100; i++)
            {
                ct.ThrowIfCancellationRequested();
                if (!Running) throw new InvalidOperationException("Engine could not start. Check administrator permission, conflicting VPNs and the imported profile.");
                try { using var socket = new TcpClient(); await socket.ConnectAsync(IPAddress.Loopback, Port, ct); return; }
                catch (SocketException) { await Task.Delay(150, ct); }
            }
            throw new InvalidOperationException("Tunnel startup timed out.");
        }
        catch { Stop(); throw; }
    }
    public async Task<long> HealthAsync(CancellationToken ct, string? url = null)
    {
        if (!Running) throw new InvalidOperationException("Engine stopped.");
        using var handler = new HttpClientHandler { Proxy = new WebProxy($"http://127.0.0.1:{Port}"), UseProxy = true, AllowAutoRedirect = false };
        using var client = new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        var urls = url == null ? new[] { "https://www.gstatic.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace" } : new[] { url };
        foreach (var target in urls)
        {
            using var budget = CancellationTokenSource.CreateLinkedTokenSource(ct);
            budget.CancelAfter(TimeSpan.FromSeconds(8));
            var timer = Stopwatch.StartNew();
            try
            {
                using var response = await client.GetAsync(target, HttpCompletionOption.ResponseHeadersRead, budget.Token);
                response.EnsureSuccessStatusCode(); return timer.ElapsedMilliseconds;
            }
            catch (HttpRequestException) { ct.ThrowIfCancellationRequested(); }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested) { }
        }
        ct.ThrowIfCancellationRequested();
        throw new InvalidOperationException("Neither HTTPS health destination responded.");
    }
    public async Task<long> DnsAsync(CancellationToken ct)
    {
        if (!Running) throw new InvalidOperationException("Engine stopped.");
        using var budget = CancellationTokenSource.CreateLinkedTokenSource(ct);
        budget.CancelAfter(TimeSpan.FromSeconds(10));
        using var socket = new UdpClient(AddressFamily.InterNetwork);
        socket.Connect("198.18.0.2", 53);
        byte[] query = Convert.FromHexString("438101000001000000000000076578616D706C6503636F6D0000010001");
        var timer = Stopwatch.StartNew();
        await socket.SendAsync(query.AsMemory(), budget.Token);
        var response = await socket.ReceiveAsync(budget.Token);
        var data = response.Buffer;
        if (data.Length < 12 || data[0] != query[0] || data[1] != query[1] ||
            (data[2] & 0x80) == 0 || (data[3] & 15) != 0 || (data[6] == 0 && data[7] == 0))
            throw new InvalidOperationException("Tunnel DNS returned no usable answer.");
        return timer.ElapsedMilliseconds;
    }
    public void Stop()
    {
        if (process != null)
        {
            try
            {
                if (!process.HasExited)
                {
                    // Attach only to our own child's console. Never signal a shared console.
                    // Console applications used by tests may already have a console: then use the job fallback.
                    if (Native.AttachConsole((uint)process.Id))
                    {
                        Native.SetConsoleCtrlHandler(IntPtr.Zero, true);
                        try { Native.GenerateConsoleCtrlEvent(0, 0); process.WaitForExit(4000); }
                        finally { Native.FreeConsole(); Native.SetConsoleCtrlHandler(IntPtr.Zero, false); }
                    }
                    if (!process.HasExited) { process.Kill(true); process.WaitForExit(4000); }
                }
            }
            catch (InvalidOperationException) { }
            catch (System.ComponentModel.Win32Exception) { /* The owned job is closed below even if the process races exit. */ }
            finally { process.Dispose(); process = null; }
        }
        if (job != IntPtr.Zero) { Native.CloseHandle(job); job = IntPtr.Zero; }
    }
    public void Dispose() => Stop();
}

internal static class Native
{
    [StructLayout(LayoutKind.Sequential)] internal struct BasicLimits
    { public long ProcessTime, JobTime; public uint LimitFlags; public UIntPtr MinWorkingSet, MaxWorkingSet; public uint ActiveProcessLimit; public UIntPtr Affinity; public uint PriorityClass, SchedulingClass; }
    [StructLayout(LayoutKind.Sequential)] internal struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)] internal struct Limits { public BasicLimits Basic; public IoCounters Io; public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] internal static extern IntPtr CreateJobObject(IntPtr attributes, string? name);
    [DllImport("kernel32.dll")] internal static extern bool SetInformationJobObject(IntPtr job, int type, ref Limits limits, uint length);
    [DllImport("kernel32.dll")] internal static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] internal static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] internal static extern bool AttachConsole(uint process);
    [DllImport("kernel32.dll")] internal static extern bool FreeConsole();
    [DllImport("kernel32.dll")] internal static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);
    [DllImport("kernel32.dll")] internal static extern bool GenerateConsoleCtrlEvent(uint kind, uint group);
}
