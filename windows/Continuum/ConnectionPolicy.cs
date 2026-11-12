using System;
using System.Linq;
using System.Net.NetworkInformation;

namespace Continuum;

public static class ConnectionPolicy
{
    // A failed public test URL is not sufficient evidence to destroy a live
    // tunnel. Restart only if the owned engine has exited or the route changed.
    public static bool NeedsRestart(bool running, string? current, string next) =>
        !running || current == null || Profile.Parse(current).Outbound().ToJsonString() != Profile.Parse(next).Outbound().ToJsonString();

    public static string UpstreamKey()
    {
        try
        {
            return string.Join("|", NetworkInterface.GetAllNetworkInterfaces()
                .Where(n => n.OperationalStatus == OperationalStatus.Up && n.Name != "Continuum" &&
                    n.NetworkInterfaceType != NetworkInterfaceType.Loopback && n.NetworkInterfaceType != NetworkInterfaceType.Tunnel)
                .Select(n => new { n.Id, Gateways = n.GetIPProperties().GatewayAddresses
                    .Select(g => g.Address.ToString()).Where(a => a != "0.0.0.0" && a != "::").OrderBy(a => a).ToArray() })
                .Where(n => n.Gateways.Length > 0).OrderBy(n => n.Id)
                .Select(n => n.Id + ":" + string.Join(",", n.Gateways)));
        }
        catch (NetworkInformationException) { return "unavailable"; }
    }
}
