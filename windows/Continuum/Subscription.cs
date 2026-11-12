using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Continuum;

public sealed class Subscription : IDisposable
{
    readonly HttpClient client;
    string? cachedUrl, cachedBody, cachedEtag;
    public Subscription(HttpMessageHandler? handler = null)
    {
        client = new HttpClient(handler ?? new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false }) { Timeout = TimeSpan.FromSeconds(20) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("Continuum-Windows/0.2");
    }
    public async Task<string> FetchAsync(string source, CancellationToken ct)
    {
        var url = new Uri(source);
        for (int redirect = 0; redirect < 6; redirect++)
        {
            if (url.Scheme != "https" || url.UserInfo.Length != 0 || url.Fragment.Length != 0)
                throw new InvalidOperationException("Subscription must be an HTTPS URL without credentials or a fragment.");
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            if (cachedUrl == url.AbsoluteUri && cachedBody != null && cachedEtag != null)
                request.Headers.TryAddWithoutValidation("If-None-Match", cachedEtag);
            using var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            if (response.StatusCode == HttpStatusCode.NotModified)
            {
                if (cachedUrl == url.AbsoluteUri && cachedBody != null) return cachedBody;
                throw new InvalidOperationException("Subscription returned an invalid cached response.");
            }
            if ((int)response.StatusCode is 301 or 302 or 303 or 307 or 308)
            {
                var location = response.Headers.Location ?? throw new InvalidOperationException("Invalid subscription redirect.");
                url = location.IsAbsoluteUri ? location : new Uri(url, location); continue;
            }
            response.EnsureSuccessStatusCode();
            if (response.Content.Headers.ContentLength > 65536) throw new InvalidOperationException("Subscription exceeds size limit.");
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
            timeout.CancelAfter(TimeSpan.FromSeconds(20));
            await using var stream = await response.Content.ReadAsStreamAsync(timeout.Token);
            using var data = new MemoryStream(); var buffer = new byte[4096]; int read;
            while ((read = await stream.ReadAsync(buffer, timeout.Token)) > 0)
            { if (data.Length + read > 65536) throw new InvalidOperationException("Subscription exceeds size limit."); await data.WriteAsync(buffer.AsMemory(0, read), timeout.Token); }
            var body = Profile.Single(Encoding.UTF8.GetString(data.ToArray()));
            cachedUrl = url.AbsoluteUri; cachedBody = body; cachedEtag = response.Headers.ETag?.ToString();
            return body;
        }
        throw new InvalidOperationException("Too many subscription redirects.");
    }
    public void Dispose() => client.Dispose();
}
