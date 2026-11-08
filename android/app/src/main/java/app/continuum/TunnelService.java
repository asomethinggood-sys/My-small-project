package app.continuum;

import android.app.*;
import android.content.*;
import android.net.*;
import android.os.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import libv2ray.*;
import go.Seq;
import org.json.JSONObject;

/** Explicit VPN lifecycle in a dedicated :vpn process, independent of bound Activities. */
public final class TunnelService extends VpnService {
    public static final String START="app.continuum.START",STOP="app.continuum.STOP",REFRESH="app.continuum.REFRESH",OBSERVE="app.continuum.OBSERVE";
    public static final int STATE=1;
    public static final String TEST_URL="https://www.gstatic.com/generate_204";
    private final Handler main=new Handler(Looper.getMainLooper());
    private final SessionGate gate=new SessionGate();
    private final ScheduledExecutorService io=Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService engine=Executors.newSingleThreadExecutor();
    private final AtomicBoolean checking=new AtomicBoolean();
    private final ArrayDeque<String> events=new ArrayDeque<>();
    private ScheduledFuture<?> scheduled;
    private SettingsStore store;
    private volatile SubscriptionClient fetcher;
    private volatile boolean stopping,destroyed,tunOpen,coreRunning;
    private volatile Profile active;
    private volatile VpnStatus status=VpnStatus.offline();
    private CoreController core;
    private ParcelFileDescriptor tun;
    private boolean nativeInitialized;
    private volatile long connectedAt;
    private int failures;
    private long lastHealth;
    private boolean refreshPending;
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback networkCallback;
    private final Messenger inbox=new Messenger(new Handler(Looper.getMainLooper(),message->{
        if(message.what==STATE&&message.replyTo!=null){
            Message reply=Message.obtain(null,STATE);Bundle b=status.bundle();b.putString("history",String.join("\n\n",events));reply.setData(b);
            try{message.replyTo.send(reply);}catch(RemoteException ignored){}
        }return true;
    }));
    @Override public IBinder onBind(Intent intent){return OBSERVE.equals(intent.getAction())?inbox.getBinder():super.onBind(intent);}
    @Override public void onCreate(){
        super.onCreate();store=new SettingsStore(this);
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("connection","VPN connection",NotificationManager.IMPORTANCE_LOW));
        connectivity=getSystemService(ConnectivityManager.class);
        networkCallback=new ConnectivityManager.NetworkCallback(){
            @Override public void onAvailable(Network network){main.post(()->requestCheck(1000));}
            @Override public void onLost(Network network){main.post(()->requestCheck(1000));}
        };
        connectivity.registerNetworkCallback(new NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN).build(),networkCallback);
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        String action=intent==null?"":intent.getAction();
        if(STOP.equals(action)){disconnect(true);return START_NOT_STICKY;}
        if(stopping)return START_NOT_STICKY;
        if(REFRESH.equals(action)){if(gate.active())requestCheck(0);else stopSelf();return gate.active()?START_STICKY:START_NOT_STICKY;}
        // Only explicit Connect can clear a saved user pause, not Always-on or sticky restarts.
        if(START.equals(action)){try{store.resumeExplicitly();}catch(Exception e){stopSelf();return START_NOT_STICKY;}}
        if(store.paused()){stopSelf();return START_NOT_STICKY;}
        startForeground(1,notification("Preparing VPN"));
        if(!gate.active()){
            long token=gate.start();
            publish(token,"Connecting","Validating the selected endpoint",-1,0);
        }
        requestCheck(0);return START_STICKY;
    }
    private Notification notification(String text){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,TunnelService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,"connection").setSmallIcon(R.drawable.ic_notification).setContentTitle("Continuum")
            .setContentText(text).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,"Disconnect",stop).build()).build();
    }
    private void event(String text){
        events.addFirst(new java.text.SimpleDateFormat("HH:mm:ss",Locale.US).format(new Date())+"  "+text);
        while(events.size()>30)events.removeLast();
    }
    private void publish(long token,String state,String detail,long delay,int seconds){
        main.post(()->{
            if(!gate.accepts(token)||stopping||destroyed)return;
            Profile p=active;
            if(!state.equals(status.state))event(state+" · "+detail);
            status=new VpnStatus(state,detail,p==null?"Waiting for endpoint":p.host,p==null?"VLESS":p.protocolLabel(),
                p==null?"WebSocket · TLS":p.transportLabel(),delay,SystemClock.elapsedRealtime()+seconds*1000L,connectedAt,true,tunOpen,coreRunning);
            if(Build.VERSION.SDK_INT<33||checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED)
                getSystemService(NotificationManager.class).notify(1,notification(state+" · "+detail));
        });
    }
    private void requestCheck(long delay){
        if(!gate.active()||stopping||destroyed||store.paused())return;
        if(checking.get()){refreshPending=true;return;}
        if(scheduled!=null)scheduled.cancel(false);
        long token=gate.current();scheduled=io.schedule(()->check(token),delay,TimeUnit.MILLISECONDS);
    }
    private void initializeNative(long token)throws Exception{
        engine.submit(()->{
            if(!gate.accepts(token))return;
            if(!nativeInitialized){Seq.setContext(getApplicationContext());Libv2ray.initCoreEnv(getFilesDir().getAbsolutePath(),"");nativeInitialized=true;}
        }).get(10,TimeUnit.SECONDS);
    }
    private long probe(Profile profile)throws Exception{
        long latency=Libv2ray.measureOutboundDelay(profile.config(false).toString(),TEST_URL);
        if(latency<0)throw new IllegalStateException("Probe failed");return latency;
    }
    private void ensureTun()throws Exception{
        if(tun!=null)return;
        tun=new Builder().setSession("Continuum").setMtu(1500)
            .addAddress("172.30.0.2",30).addRoute("0.0.0.0",0)
            .addAddress("fd66:6f6e:7469::2",126).addRoute("::",0)
            .addDnsServer("1.1.1.1").addDnsServer("2606:4700:4700::1111")
            .addDisallowedApplication(getPackageName()).setBlocking(false).establish();
        if(tun==null)throw new IllegalStateException("VPN consent required");tunOpen=true;
    }
    private CoreController controller(){return Libv2ray.newCoreController(new CoreCallbackHandler(){
        public long startup(){return 0;}public long shutdown(){return 0;}public long onEmitStatus(long code,String text){return 0;}
    });}
    private boolean install(Profile next,long token)throws Exception{
        return engine.submit(()->{
            if(!gate.accepts(token)||store.paused())return false;
            Profile previous=active;
            ensureTun();if(core==null)core=controller();
            if(core.getIsRunning())core.stopLoop();coreRunning=false;
            try{
                if(!gate.accepts(token))return false;
                core.startLoop(next.config(true).toString(),tun.getFd());
                if(!gate.accepts(token)){shutdownEngine();return false;}
                if(!core.getIsRunning())throw new IllegalStateException("Engine did not start");
                coreRunning=true;active=next;if(connectedAt==0)connectedAt=SystemClock.elapsedRealtime();return true;
            }catch(Exception error){
                if(previous!=null&&gate.accepts(token)){
                    try{core.stopLoop();core.startLoop(previous.config(true).toString(),tun.getFd());coreRunning=core.getIsRunning();}catch(Exception ignored){}
                }
                throw error;
            }
        }).get(15,TimeUnit.SECONDS);
    }
    private void check(long token){
        if(!gate.accepts(token)||!checking.compareAndSet(false,true))return;
        int interval=60;
        try{
            JSONObject settings=store.load();interval=settings.optInt("interval",60);if(interval!=30&&interval!=60&&interval!=120)interval=60;
            String manual=SettingsStore.manual(settings),source=settings.optString("source",SubscriptionClient.DEFAULT);
            String content=manual;boolean cached=false;
            if(manual==null){
                SubscriptionClient client=new SubscriptionClient();fetcher=client;
                try{content=client.fetch(source);}catch(Exception error){
                    if(!gate.accepts(token))return;
                    if(active!=null&&coreRunning){
                        // Fetch failure is not evidence of a healthy VPN. Verify before labelling connected.
                        long latency=probe(active);lastHealth=SystemClock.elapsedRealtime();
                        publish(token,"Connected","Update unavailable; endpoint check passed",latency,interval);return;
                    }
                    content=store.cache(source);if(content.isEmpty())throw error;cached=true;
                }finally{fetcher=null;}
            }
            if(!gate.accepts(token))return;
            Profile candidate=Profile.subscription(content);
            boolean same=active!=null&&active.key().equals(candidate.key());
            if(same&&coreRunning&&failures==0&&SystemClock.elapsedRealtime()-lastHealth<300000){
                publish(token,"Connected",candidate.protocolLabel()+" · "+candidate.transportLabel(),status.latency,interval);return;
            }
            initializeNative(token);if(!gate.accepts(token))return;
            if(!same)publish(token,coreRunning?"Checking update":"Connecting","Testing before replacing the active profile",status.latency,interval);
            long latency=probe(candidate);if(!gate.accepts(token))return;
            boolean repair=same&&failures>0;
            if(!same||!coreRunning||repair){
                publish(token,"Switching","Installing a verified endpoint",latency,interval);
                if(!install(candidate,token))return;
                if(manual==null&&!cached&&gate.accepts(token))store.cache(source,content);
            }
            failures=0;lastHealth=SystemClock.elapsedRealtime();
            publish(token,"Connected",cached?"Using last verified profile; subscription unavailable":candidate.protocolLabel()+" · "+candidate.transportLabel(),latency,interval);
        }catch(Exception error){
            if(!gate.accepts(token))return;
            failures++;interval=RotationPolicy.retrySeconds(failures);
            publish(token,coreRunning?"Checking connection":"Reconnecting",
                error instanceof IllegalArgumentException?"Invalid profile rejected; no update installed":"Connection check failed; retry scheduled",-1,interval);
        }catch(LinkageError error){
            main.post(()->{if(gate.accepts(token)){event("Native engine unavailable on this device");disconnect(true);}});
        }finally{
            checking.set(false);final int seconds=interval;
            main.post(()->{
                if(stopping||destroyed||!gate.active())return;
                // A newer Connect may have queued behind this cancelled generation's probe.
                // Never drop that pending request merely because the old token is stale.
                boolean pending=refreshPending||!gate.accepts(token);refreshPending=false;
                requestCheck(pending?0:seconds*1000L);
            });
        }
    }
    private void disconnect(boolean user){
        if(user){try{store.pause();}catch(Exception ignored){event("Could not save pause preference");}}
        gate.stop();refreshPending=false;if(scheduled!=null)scheduled.cancel(true);
        if(stopping)return;stopping=true;
        status=new VpnStatus("Disconnecting","Closing VPN resources",status.host,status.protocol,status.transport,-1,0,0,true,tunOpen,coreRunning);
        SubscriptionClient client=fetcher;if(client!=null)new Thread(client::cancel,"cancel-subscription").start();
        // The manifest isolates this watchdog from the UI process.
        Runnable watchdog=()->{
            if(!stopping)return;
            getSystemService(NotificationManager.class).cancel(1);stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();
            android.os.Process.killProcess(android.os.Process.myPid());
        };
        main.postDelayed(watchdog,2500);
        engine.execute(()->{
            shutdownEngine();
            main.post(()->{
                main.removeCallbacks(watchdog);stopping=false;connectedAt=0;active=null;
                status=VpnStatus.offline();event("Disconnected; explicit Connect is required to resume");
                stopForeground(STOP_FOREGROUND_REMOVE);getSystemService(NotificationManager.class).cancel(1);stopSelf();
            });
        });
    }
    private void shutdownEngine(){
        try{if(tun!=null)tun.close();}catch(Exception ignored){}tun=null;tunOpen=false;
        try{if(core!=null)core.stopLoop();}catch(Exception ignored){}core=null;coreRunning=false;
    }
    @Override public void onRevoke(){disconnect(true);}
    @Override public void onDestroy(){
        destroyed=true;gate.stop();if(scheduled!=null)scheduled.cancel(true);
        try{connectivity.unregisterNetworkCallback(networkCallback);}catch(Exception ignored){}
        if(!stopping)engine.execute(this::shutdownEngine);
        io.shutdownNow();engine.shutdown();super.onDestroy();
    }
}
