using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Forms = System.Windows.Forms;

namespace Continuum;
public partial class MainWindow : Window
{
    readonly Engine engine = new();
    readonly Subscription subscription = new();
    readonly SemaphoreSlim operation = new(1, 1);
    readonly DispatcherTimer timer = new() { Interval = TimeSpan.FromSeconds(20) };
    readonly Forms.NotifyIcon tray;
    CancellationTokenSource work = new();
    Settings settings;
    bool wanted, closing, stopped;
    string? active;
    DateTime nextFetch = DateTime.MinValue, retryAt = DateTime.MinValue;
    int failures;
    public MainWindow()
    {
        InitializeComponent();
        settings = Settings.Load(); SourceText.Text = settings.Source; SourceMode.SelectedIndex = settings.Imported ? 1 : 0;
        Mtu.SelectedIndex = settings.Mtu == 1280 ? 0 : settings.Mtu == 1500 ? 2 : 1;
        tray = new Forms.NotifyIcon { Text = "Continuum — disconnected", Icon = System.Drawing.SystemIcons.Application, Visible = true };
        var menu = new Forms.ContextMenuStrip();
        menu.Items.Add("Open Continuum", null, (_, _) => Dispatcher.Invoke(ShowWindow));
        menu.Items.Add("Disconnect", null, (_, _) => Dispatcher.InvokeAsync(async () => await Disconnect()));
        menu.Items.Add("Exit", null, (_, _) => Dispatcher.Invoke(Close)); tray.ContextMenuStrip = menu;
        tray.DoubleClick += (_, _) => Dispatcher.Invoke(ShowWindow);
        timer.Tick += async (_, _) => { if (wanted && DateTime.UtcNow >= retryAt) await Maintain(false); };
        timer.Start(); NetworkChange.NetworkAddressChanged += NetworkChanged;
        Closing += OnClosing;
        System.Windows.Application.Current.SessionEnding += (_, _) => { wanted = false; work.Cancel(); engine.Stop(); };
    }
    void ShowWindow() { Show(); WindowState = WindowState.Normal; Activate(); }
    void NetworkChanged(object? sender, EventArgs e) => Dispatcher.BeginInvoke(new Action(() => { nextFetch = DateTime.MinValue; retryAt = DateTime.MinValue; }));
    void Editable(bool enabled) { SourceText.IsEnabled = enabled; SourceMode.IsEnabled = enabled; Mtu.IsEnabled = enabled; }
    void State(string title, string detail, bool connected = false)
    {
        StatusTitle.Text = title; StatusDetail.Text = detail; OrbText.Text = connected ? "✓" : "○";
        tray.Text = connected ? "Continuum — connected" : "Continuum — " + (wanted ? "connecting" : "disconnected");
    }
    async void ToggleConnection(object sender, RoutedEventArgs e)
    {
        if (wanted) { await Disconnect(); return; }
        settings = new(SourceText.Text.Trim(), SourceMode.SelectedIndex == 1, Mtu.SelectedIndex == 0 ? 1280 : Mtu.SelectedIndex == 2 ? 1500 : 1400);
        try
        {
            if (settings.Imported) Profile.Single(settings.Source);
            else if (!Uri.TryCreate(settings.Source, UriKind.Absolute, out var uri) || uri.Scheme != "https") throw new FormatException();
            settings.Save();
        }
        catch { State("Check your settings", "Enter a valid HTTPS subscription or supported connection link. Settings must be writable."); return; }
        work.Dispose(); work = new(); wanted = true; active = null; failures = 0;
        Editable(false); ConnectButton.Content = "Disconnect"; CheckButton.IsEnabled = true;
        await Maintain(true);
    }
    async Task Maintain(bool force)
    {
        if (!wanted || !await operation.WaitAsync(0)) return;
        var ct = work.Token;
        try
        {
            if (force || active == null || (!settings.Imported && DateTime.UtcNow >= nextFetch))
            {
                State(engine.Running ? "Checking for updates" : "Connecting", "Retrieving and validating your connection profile.");
                string next;
                try { next = settings.Imported ? Profile.Single(settings.Source) : await subscription.FetchAsync(settings.Source, ct); nextFetch = DateTime.UtcNow.AddMinutes(5); }
                catch when (active != null && engine.Running && !ct.IsCancellationRequested)
                { next = active; nextFetch = DateTime.UtcNow.AddMinutes(1); }
                ct.ThrowIfCancellationRequested();
                if (next != active || !engine.Running)
                {
                    await engine.StartAsync(Profile.Parse(next), true, settings.Mtu, ct);
                    active = next;
                }
            }
            else if (!engine.Running && active != null)
                await engine.StartAsync(Profile.Parse(active), true, settings.Mtu, ct);
            var elapsed = await engine.HealthAsync(ct);
            ct.ThrowIfCancellationRequested();
            if (!wanted) return;
            failures = 0; retryAt = DateTime.MinValue;
            Latency.Text = $"HTTPS CHECK  {elapsed:N0} ms";
            State("Connected", $"{Profile.Parse(active!).Protocol.ToUpperInvariant()} · device-wide tunnel\nYour connection is responding.", true);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { }
        catch
        {
            if (!wanted) return;
            failures++;
            // Keep a running tunnel after a failed health endpoint. Only recycle
            // after three failures; a single check is not proof the route died.
            if (failures >= 3) engine.Stop();
            retryAt = DateTime.UtcNow.AddSeconds(Math.Min(300, 10 * Math.Pow(2, Math.Min(failures, 5))));
            State("Connection unavailable", "The route did not pass its HTTPS check. Retrying with bounded backoff; Disconnect stops retries. Check your source, network and other VPNs.");
            Latency.Text = "HTTPS CHECK  unavailable";
        }
        finally { operation.Release(); }
    }
    async Task Disconnect()
    {
        wanted = false; work.Cancel(); ConnectButton.IsEnabled = false;
        await operation.WaitAsync();
        try { engine.Stop(); active = null; State("Disconnected", "The tunnel is closed. Automatic reconnect is paused."); Latency.Text = "HTTPS CHECK  —"; }
        finally { operation.Release(); Editable(true); ConnectButton.IsEnabled = true; ConnectButton.Content = "Connect"; CheckButton.IsEnabled = false; }
    }
    async void CheckNow(object sender, RoutedEventArgs e) { retryAt = DateTime.MinValue; await Maintain(true); }
    void UseDefault(object sender, RoutedEventArgs e)
    { if (!wanted) { SourceMode.SelectedIndex = 0; SourceText.Text = Settings.DefaultSource; } }
    void MinimizeToTray(object sender, RoutedEventArgs e) => Hide();
    async void OnClosing(object? sender, CancelEventArgs e)
    {
        if (stopped) return;
        e.Cancel = true; if (closing) return; closing = true;
        timer.Stop(); NetworkChange.NetworkAddressChanged -= NetworkChanged;
        await Disconnect(); tray.Dispose(); subscription.Dispose(); engine.Dispose(); work.Dispose();
        stopped = true; Close();
    }
}
