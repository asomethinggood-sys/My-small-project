package app.continuum;

import android.app.*;
import android.content.*;
import android.net.*;
import android.os.*;
import java.util.*;
import java.util.concurrent.*;
import libv2ray.*;
import go.Seq;

public final class TunnelService extends VpnService {
    public static final String STOP="app.continuum.STOP", REFRESH="app.continuum.REFRESH";
    public static final String TEST_URL="https://www.gstatic.com/generate_204";
    public static final class Snapshot {
        public final String state, detail, host;
        public final long latency, nextCheck, connectedAt;
        public final boolean running;
        Snapshot(String s,String d,String h,long l,long n,long c,boolean r) {
            state=s;detail=d;host=h;latency=l;nextCheck=n;connectedAt=c;running=r;
        }
    }
    public static volatile Snapshot snapshot=new Snapshot("Offline","Ready when you are","No active endpoint",-1,0,0,false);
    private static final List<String> events=new ArrayList<>();
    public static synchronized String history() { return String.join("\n\n",events); }
    private static synchronized void event(String text) {
        events.add(0,new java.text.SimpleDateFormat("HH:mm:ss",Locale.US).format(new Date())+"  "+text);
        if(events.size()>40) events.remove(events.size()-1);
    }
    private final ScheduledExecutorService executor=Executors.newSingleThreadScheduledExecutor();
    private final Object scheduleLock=new Object();
    private final Object lifecycleLock=new Object();
    private ScheduledFuture<?> next;
    private volatile boolean wanted=false, destroyed=false;
    private CoreController core;
    private ParcelFileDescriptor tun;
    private Profile active;
    private SharedPreferences prefs;
    private int failures=0;
    private long connectedAt=0;
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback callback;

    @Override public void onCreate() {
        super.onCreate(); prefs=getSharedPreferences("continuum",MODE_PRIVATE);
        NotificationManager nm=getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("connection","Connection",NotificationManager.IMPORTANCE_LOW));
        connectivity=getSystemService(ConnectivityManager.class);
        callback=new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network network) { if(wanted) schedule(1000); }
            @Override public void onLost(Network network) { if(wanted) schedule(1000); }
        };
        connectivity.registerNetworkCallback(new NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN).build(),callback);
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent!=null && STOP.equals(intent.getAction())) { stopRequested(); return START_NOT_STICKY; }
        // Android's Always-on VPN start is explicit permission to recover; a sticky restart
        // respects the user's saved stop preference.
        boolean systemStart=intent!=null && VpnService.SERVICE_INTERFACE.equals(intent.getAction());
        if(intent==null && !prefs.getBoolean("wanted",false)) { stopSelf(); return START_NOT_STICKY; }
        wanted=true; prefs.edit().putBoolean("wanted",true).apply();
        startForeground(1,notification("Preparing secure connection"));
        if (intent!=null && REFRESH.equals(intent.getAction())) event("Manual subscription check");
        if(systemStart) event("Android Always-on requested recovery");
        schedule(0);
        return START_STICKY;
    }
    private Notification notification(String text) {
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,TunnelService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,"connection").setSmallIcon(app.continuum.R.drawable.ic_continuum)
            .setContentTitle("Continuum").setContentText(text).setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null,"Disconnect",stop).build()).build();
    }
    private void publish(String state,String detail,long latency,int seconds) {
        if(!wanted) return;
        Snapshot old=snapshot;
        snapshot=new Snapshot(state,detail,active==null?"Waiting for endpoint":active.host,latency,
            SystemClock.elapsedRealtime()+seconds*1000L,connectedAt,true);
        if(!state.equals(old.state)) event(state+" · "+detail);
        if(Build.VERSION.SDK_INT<33 || checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
            ==android.content.pm.PackageManager.PERMISSION_GRANTED)
            getSystemService(NotificationManager.class).notify(1,notification(state+" · "+detail));
    }
    private void schedule(long delay) {
        synchronized(scheduleLock) {
            if(!wanted || destroyed) return;
            if(next!=null) next.cancel(false);
            next=executor.schedule(this::tick,delay,TimeUnit.MILLISECONDS);
        }
    }
    private void setup() throws Exception { synchronized(lifecycleLock) {
        if(!wanted || destroyed) throw new IllegalStateException("Stopping");
        if(tun==null) {
            tun=new Builder().setSession("Continuum").setMtu(1500)
                .addAddress("172.30.0.2",30).addRoute("0.0.0.0",0)
                .addAddress("fd66:6f6e:7469::2",126).addRoute("::",0)
                .addDnsServer("1.1.1.1").addDnsServer("2606:4700:4700::1111")
                // The app's control-plane and native core sockets must bypass their own TUN.
                .addDisallowedApplication(getPackageName()).setBlocking(false).establish();
            if(tun==null) throw new IllegalStateException("VPN permission is required");
        }
        if(core==null) {
            Seq.setContext(getApplicationContext());
            Libv2ray.initCoreEnv(getFilesDir().getAbsolutePath(),"");
            core=Libv2ray.newCoreController(new CoreCallbackHandler() {
                public long startup(){return 0;}
                public long shutdown(){return 0;}
                public long onEmitStatus(long code,String status){return 0;}
            });
        }
    }
    }
    private boolean running() { return core!=null && core.getIsRunning(); }
    private long verify(Profile p) throws Exception {
        long result=Libv2ray.measureOutboundDelay(p.config(false).toString(),TEST_URL);
        if(result<0) throw new IllegalStateException("Connection check failed");
        return result;
    }
    private void install(Profile candidate) throws Exception { synchronized(lifecycleLock) {
        Profile previous=active;
        if(!wanted) return;
        if(running()) core.stopLoop();
        try {
            core.startLoop(candidate.config(true).toString(),tun.getFd());
            if(!running()) throw new IllegalStateException("VPN engine did not start");
            active=candidate;
            if(connectedAt==0) connectedAt=SystemClock.elapsedRealtime();
        } catch(Exception failure) {
            // Best-effort rollback without closing the Android VPN interface.
            try {
                core.stopLoop();
                if(previous!=null && wanted) core.startLoop(previous.config(true).toString(),tun.getFd());
            } catch(Exception ignored) { event("Rollback unavailable; waiting for a working endpoint"); }
            throw failure;
        }
    }
    }
    private void tick() {
        if(!wanted || destroyed) return;
        int delay=prefs.getInt("interval",60);
        String source=prefs.getString("source",SubscriptionClient.DEFAULT);
        try {
            setup();
            if(active==null) publish("Connecting","Checking the subscription",-1,delay);
            String content;
            try { content=new SubscriptionClient().fetch(source); }
            catch(Exception fetchError) {
                // Startup can recover from a previously verified, privately cached profile.
                String cached=prefs.getString("verified","");
                if(active==null && !cached.isEmpty()) {
                    Profile last=Profile.subscription(cached);
                    long measured=verify(last);
                    if(!wanted) return;
                    install(last);
                    publish("Connected","Using last verified profile; update unavailable",measured,delay);
                }
                throw fetchError;
            }
            Profile candidate=Profile.subscription(content);
            if(!wanted) return;
            boolean same=active!=null && active.key().equals(candidate.key());
            if(!same) publish(active==null?"Connecting":"Checking update",
                active==null?"Testing the endpoint":"Current profile stays active during this check",snapshot.latency,delay);
            // Run a separate outbound-only probe before touching the active TUN engine.
            long measured;
            boolean repair=false;
            if(same && running()) {
                try { measured=core.measureDelay(TEST_URL); if(measured<0)throw new IllegalStateException(); }
                catch(Exception healthFailure) {
                    if(failures<1) throw healthFailure;
                    measured=verify(candidate); repair=true;
                }
            } else measured=verify(candidate);
            if(!wanted) return;
            RotationPolicy.Decision choice=RotationPolicy.decide(active,candidate,true,running());
            if(choice==RotationPolicy.Decision.INSTALL || repair) {
                publish("Switching","Validated endpoint; existing sessions may reconnect",measured,delay);
                install(candidate);
                if(!wanted) return;
                prefs.edit().putString("verified",content).apply();
                event(same?"Recovered VPN engine":"Installed a verified endpoint");
            }
            failures=0;
            publish("Connected","VLESS · WebSocket · TLS",measured,delay);
        } catch(Exception error) {
            if(!wanted) return;
            failures++;
            delay=RotationPolicy.retrySeconds(failures);
            // No unverified update replaces the old profile. Do not label a failed probe as connected.
            String detail=error instanceof IllegalArgumentException?"Invalid or unsupported subscription; no update installed":"Endpoint or subscription unavailable";
            publish("Reconnecting",detail+" · retry in "+delay+"s",-1,delay);
        } finally { if(wanted && !destroyed) schedule(delay*1000L); }
    }
    private void stopRequested() {
        wanted=false; prefs.edit().putBoolean("wanted",false).apply(); stopSelf();
    }
    @Override public void onRevoke() { stopRequested(); }
    @Override public void onDestroy() {
        wanted=false; destroyed=true;
        synchronized(scheduleLock) { if(next!=null) next.cancel(false); }
        if(callback!=null) connectivity.unregisterNetworkCallback(callback);
        // Teardown must not wait behind a slow subscription fetch/probe on the scheduler.
        snapshot=new Snapshot("Disconnecting","Closing the VPN interface",snapshot.host,-1,0,0,true);
        new Thread(()->{
            synchronized(lifecycleLock) {
                try { if(core!=null) core.stopLoop(); } catch(Exception ignored) {}
                try { if(tun!=null) tun.close(); } catch(Exception ignored) {}
                core=null; tun=null;
            }
            snapshot=new Snapshot("Offline","Disconnected","No active endpoint",-1,0,0,false);
            event("Disconnected");
        },"continuum-stop").start();
        executor.shutdown();
        stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy();
    }
}
