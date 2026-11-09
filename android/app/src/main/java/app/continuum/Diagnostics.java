package app.continuum;

import android.os.*;
import java.util.Locale;

/** Local, allowlisted report. No URLs, hostnames, credentials, IPs, SSIDs or raw exceptions. */
public final class Diagnostics {
    private static volatile String outcome="Not checked";
    private static volatile long duration=-1;
    private Diagnostics(){}
    public static void success(long elapsed){outcome="Endpoint HTTPS succeeded (not a full-device DNS/traffic test)";duration=elapsed;RustCore.addMetric(1,1);}
    public static void failure(Throwable error){
        int mask=0;
        for(int depth=0;error!=null&&depth<8;depth++,error=error.getCause()){
            String text=(error.getClass().getSimpleName()+" "+String.valueOf(error.getMessage())).toLowerCase(Locale.ROOT);
            if(text.contains("unknownhost")||text.contains("lookup ")||text.contains("dns"))mask|=1;
            if(text.contains("certificate")||text.contains("x509")||text.contains("tls")||text.contains("ssl"))mask|=2;
            if(text.contains("timeout")||text.contains("timed out")||text.contains("deadline"))mask|=4;
            if(text.contains("refused")||text.contains("unreachable")||text.contains("no route"))mask|=8;
        }
        String[] labels={"Unclassified check failure","DNS-related check failure","TLS/certificate-related check failure","Check timed out","Endpoint/network unreachable"};
        outcome=labels[RustCore.classify(mask)]+" (classification is heuristic)";duration=-1;
    }
    public static String report(VpnStatus status){
        return "Continuum "+BuildConfig.VERSION_NAME+" · "+BuildConfig.BUILD_ABI+"\n"+
            "Android API: "+Build.VERSION.SDK_INT+"\n"+
            "TUN open: "+status.tunOpen+"; engine running: "+status.engineRunning+"\n"+
            "Last check: "+outcome+"\nCheck operation duration: "+duration+" ms (not ping)\n"+
            "Default-network transitions (includes initial discovery): "+RustCore.metric(0)+"\n"+
            "Successful endpoint checks: "+RustCore.metric(1)+"\n"+
            "Fetched subscription bodies: "+RustCore.metric(2)+"; HTTP 304 reuse: "+RustCore.metric(3)+"\n"+
            "VPN-process cumulative CPU: "+android.os.Process.getElapsedCpuTime()+" ms\n"+
            "VPN-process current PSS: "+Debug.getPss()+" KiB\n"+
            "Counters are process-local and reset on process death. PSS/CPU snapshots are not battery savings or idle-rate measurements.\n"+
            "No configuration credentials, destination history, network names or endpoint addresses included.";
    }
}
