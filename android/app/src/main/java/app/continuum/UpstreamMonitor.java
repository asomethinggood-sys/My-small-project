package app.continuum;

import android.net.*;

/** Register as a DEFAULT network callback: unrelated Wi-Fi/cellular events do not churn checks. */
public final class UpstreamMonitor extends ConnectivityManager.NetworkCallback {
    private final ConnectivityManager manager;
    private final Runnable changed;
    private Network current;
    public UpstreamMonitor(ConnectivityManager manager,Runnable changed){this.manager=manager;this.changed=changed;}
    @Override public void onAvailable(Network network){NetworkCapabilities c=manager.getNetworkCapabilities(network);if(c!=null)onCapabilitiesChanged(network,c);}
    @Override public synchronized void onCapabilitiesChanged(Network network,NetworkCapabilities c){
        if(c.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)&&c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))select(network);
        else if(network.equals(current))select(null);
    }
    @Override public synchronized void onLost(Network network){if(network.equals(current))select(null);}
    private void select(Network next){
        long previous=current==null?-1:current.getNetworkHandle(),selected=next==null?-1:next.getNetworkHandle();
        if(!RustCore.networkChanged(previous,selected))return;
        current=next;RustCore.addMetric(0,1);changed.run();
    }
}
