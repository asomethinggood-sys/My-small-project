package app.continuum;

import android.app.*;
import android.content.*;
import android.net.*;
import android.os.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import libv2ray.*;
import go.Seq;
import org.json.JSONObject;

/** Android lifecycle adapter in :vpn. Policy/token decisions cross a primitive Rust JNI ABI. */
public final class TunnelService extends VpnService {
    public static final String START="app.continuum.START",STOP="app.continuum.STOP",REFRESH="app.continuum.REFRESH",OBSERVE="app.continuum.OBSERVE";
    public static final int STATE=1,UNOBSERVE=2;
    public static final String TEST_URL="https://www.gstatic.com/generate_204";
    private static final String FALLBACK_TEST_URL="https://cp.cloudflare.com/generate_204";
    private final Handler main=new Handler(Looper.getMainLooper());
    private final SessionGate gate=new SessionGate();
    private final ScheduledExecutorService io=Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService engine=Executors.newSingleThreadExecutor();
    private final AtomicBoolean checking=new AtomicBoolean();
    private final AtomicLong checkEpoch=new AtomicLong();
    private final ArrayDeque<String> events=new ArrayDeque<>();
    private final Map<IBinder,Messenger> observers=new HashMap<>();
    private ScheduledFuture<?> scheduled;
    private SettingsStore store;
    private volatile SubscriptionClient fetcher;
    private volatile CountryClient countryFetcher;
    private volatile CountryClient.Lease countryLease;
    private volatile CountryClient.Source leaseSource;
    private volatile String countryBinding="";
    private final ExecutorService leaseCleanup=Executors.newSingleThreadExecutor();
    private volatile boolean stopping,destroyed,tunOpen,coreRunning;
    private volatile Profile active;
    private volatile VpnStatus status=VpnStatus.offline();
    private CoreController core;
    private ParcelFileDescriptor tun;
    private int tunMtu;
    private String installedOptions="",nativeConfig="";
    private boolean nativeInitialized,refreshPending;
    private volatile long connectedAt;
    private int failures;
    private long lastHealth,healthyEpoch=-1;
    private String lastNotification="";
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback networkCallback;
    private final Messenger inbox=new Messenger(new Handler(Looper.getMainLooper(),message->{
        if(message.replyTo!=null){
            IBinder key=message.replyTo.getBinder();
            if(message.what==UNOBSERVE)observers.remove(key);
            else if(message.what==STATE){if(observers.size()<16||observers.containsKey(key))observers.put(key,message.replyTo);send(message.replyTo);}
        }return true;
    }));
    private boolean send(Messenger target){
        Message reply=Message.obtain(null,STATE);Bundle b=status.bundle();
        b.putString("history",String.join("\n\n",events));b.putString("diagnostics",Diagnostics.report(status));reply.setData(b);
        try{target.send(reply);return true;}catch(RemoteException ignored){return false;}
    }
    private void broadcast(){observers.values().removeIf(observer->!send(observer));}
    @Override public IBinder onBind(Intent intent){return OBSERVE.equals(intent.getAction())?inbox.getBinder():super.onBind(intent);}
    @Override public void onCreate(){
        super.onCreate();store=new SettingsStore(this);
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("connection","VPN connection",NotificationManager.IMPORTANCE_LOW));
        connectivity=getSystemService(ConnectivityManager.class);
        networkCallback=new UpstreamMonitor(connectivity,()->{
            SubscriptionClient.forceNext();checkEpoch.incrementAndGet();main.post(()->requestCheck(750));
        });
        connectivity.registerDefaultNetworkCallback(networkCallback);
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        String action=intent==null?"":intent.getAction();
        if(STOP.equals(action)){disconnect(true);return START_NOT_STICKY;}
        if(stopping)return START_NOT_STICKY;
        if(REFRESH.equals(action)){
            SubscriptionClient.forceNext();checkEpoch.incrementAndGet();
            if(gate.active())requestCheck(0);else stopSelf();return gate.active()?START_STICKY:START_NOT_STICKY;
        }
        if(START.equals(action)){try{store.resumeExplicitly();SubscriptionClient.forceNext();}catch(Exception e){stopSelf();return START_NOT_STICKY;}}
        if(store.paused()){stopSelf();return START_NOT_STICKY;}
        startForeground(1,notification("Preparing VPN"));lastNotification="";
        if(!gate.active()){long token=gate.start();checkEpoch.incrementAndGet();publish(token,"Connecting","Starting the selected profile",-1,0);}
        requestCheck(0);return START_STICKY;
    }
    private Notification notification(String text){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,TunnelService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,"connection").setSmallIcon(R.drawable.ic_notification).setContentTitle("Nyx VPN")
            .setContentText(text).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,"Disconnect",stop).build()).build();
    }
    private void event(String text){events.addFirst(new java.text.SimpleDateFormat("HH:mm:ss",Locale.US).format(new Date())+"  "+text);while(events.size()>30)events.removeLast();}
    private void publish(long token,String state,String detail,long delay,int seconds){
        main.post(()->{
            if(!gate.accepts(token)||stopping||destroyed)return;
            Profile p=active;if(!state.equals(status.state))event(state+" · "+detail);
            status=new VpnStatus(state,detail,p==null?"Waiting for endpoint":p.host,p==null?"VLESS":p.protocolLabel(),
                p==null?"WebSocket · TLS":p.transportLabel(),delay,SystemClock.elapsedRealtime()+seconds*1000L,connectedAt,true,tunOpen,coreRunning);
            broadcast();String text=state+" · "+detail;
            if(!text.equals(lastNotification)&&(Build.VERSION.SDK_INT<33||checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED)){
                getSystemService(NotificationManager.class).notify(1,notification(text));lastNotification=text;
            }
        });
    }
    private void requestCheck(long delay){
        if(!gate.active()||stopping||destroyed||store.paused())return;
        if(checking.get()){refreshPending=true;return;}
        if(scheduled!=null)scheduled.cancel(false);
        long token=gate.current();scheduled=io.schedule(()->check(token),delay,TimeUnit.MILLISECONDS);
    }
    private boolean upstreamAvailable(){
        Network network=connectivity.getActiveNetwork();NetworkCapabilities c=network==null?null:connectivity.getNetworkCapabilities(network);
        return c!=null&&c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)&&c.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN);
    }
    private void initializeNative(long token)throws Exception{
        engine.submit(()->{
            if(!gate.accepts(token))return;
            if(!nativeInitialized){Seq.setContext(getApplicationContext());Libv2ray.initCoreEnv(getFilesDir().getAbsolutePath(),"");nativeInitialized=true;}
        }).get(10,TimeUnit.SECONDS);
    }
    private long candidateProbe(Profile profile,long token)throws Exception{
        Exception failure=null;
        for(String url:new String[]{TEST_URL,FALLBACK_TEST_URL}){
            if(!gate.accepts(token))throw new InterruptedException();
            try{long latency=Libv2ray.measureOutboundDelay(profile.config(false).toString(),url);if(latency>=0)return latency;}catch(Exception e){failure=e;}
        }throw new IllegalStateException("Endpoint checks failed",failure);
    }
    private long activeProbe(long token)throws Exception{
        return engine.submit(()->{
            if(!gate.accepts(token))throw new InterruptedException();
            if(core==null||!core.getIsRunning()){coreRunning=false;throw new IllegalStateException("Engine stopped");}
            Exception failure=null;
            for(String url:new String[]{TEST_URL,FALLBACK_TEST_URL}){
                if(!gate.accepts(token))throw new InterruptedException();
                try{long latency=core.measureDelay(url);if(latency>=0)return latency;}catch(Exception e){failure=e;}
            }throw new IllegalStateException("Active engine checks failed",failure);
        }).get(30,TimeUnit.SECONDS);
    }
    private void ensureTun(int mtu)throws Exception{
        if(tun!=null&&tunMtu==mtu)return;
        ParcelFileDescriptor next=new Builder().setSession("Nyx VPN").setMtu(mtu)
            .addAddress("172.30.0.2",30).addRoute("0.0.0.0",0).addAddress("fd66:6f6e:7469::2",126).addRoute("::",0)
            .addDnsServer(NetworkConfig.DNS_ADDRESS).addDisallowedApplication(getPackageName()).setBlocking(false).establish();
        if(next==null)throw new IllegalStateException("VPN consent required");
        if(tun!=null)tun.close();tun=next;tunMtu=mtu;tunOpen=true;
    }
    private CoreController controller(){return Libv2ray.newCoreController(new CoreCallbackHandler(){public long startup(){return 0;}public long shutdown(){return 0;}public long onEmitStatus(long code,String text){return 0;}});}
    private boolean install(Profile next,JSONObject options,long token)throws Exception{
        final String config=NetworkConfig.tunnel(next,options).toString();
        return engine.submit(()->{
            if(!gate.accepts(token)||store.paused())return false;
            String previous=nativeConfig;int previousMtu=tunMtu;
            if(core==null)core=controller();if(core.getIsRunning())core.stopLoop();coreRunning=false;
            try{
                if(!gate.accepts(token))return false;
                ensureTun(NetworkConfig.mtu(options));core.startLoop(config,tun.getFd());
                if(!gate.accepts(token)){shutdownEngine();return false;}
                if(!core.getIsRunning())throw new IllegalStateException("Engine did not start");
                coreRunning=true;active=next;nativeConfig=config;installedOptions=NetworkConfig.identity(options);
                if(connectedAt==0)connectedAt=SystemClock.elapsedRealtime();return true;
            }catch(Exception error){
                if(!previous.isEmpty()&&gate.accepts(token)){try{core.stopLoop();ensureTun(previousMtu);core.startLoop(previous,tun.getFd());coreRunning=core.getIsRunning();}catch(Exception ignored){}}
                throw error;
            }
        }).get(15,TimeUnit.SECONDS);
    }
    private void retireCountry(){
        CountryClient.Lease old=countryLease;CountryClient.Source source=leaseSource;
        countryLease=null;leaseSource=null;countryBinding="";
        retire(old,source);
    }
    private void retire(CountryClient.Lease lease,CountryClient.Source source){
        if(lease==null||source==null||leaseCleanup.isShutdown())return;
        leaseCleanup.execute(()->{try{new CountryClient(source).release(lease);}catch(Exception ignored){/* Backend enforces expiry independently. */}});
    }
    private void stopPayload(){
        try{if(core!=null)core.stopLoop();}catch(Exception ignored){}
        core=null;coreRunning=false;nativeConfig="";installedOptions="";active=null;connectedAt=0;
        // Keep TUN open: unavailable country traffic must not escape to default.
    }
    private void watchLease(CountryClient.Lease lease,long token){
        main.postDelayed(()->{
            if(!gate.accepts(token)||countryLease!=lease)return;
            engine.execute(()->{if(gate.accepts(token)&&countryLease==lease){stopPayload();publish(token,"Country expired","Traffic blocked; renewing country session",-1,1);}});
            requestCheck(0);
        },Math.max(0,lease.deadline-SystemClock.elapsedRealtime()));
    }
    private void checkCountry(JSONObject settings,long token)throws Exception{
        String country=settings.getString("country");
        String binding;
        try{binding=CountryClient.binding(settings);}catch(Exception invalid){
            retireCountry();engine.submit(()->{if(!gate.accepts(token))return;stopPayload();try{ensureTun(NetworkConfig.mtu(settings));}catch(Exception e){throw new IllegalStateException(e);}}).get(15,TimeUnit.SECONDS);throw invalid;
        }
        CountryClient.Lease old=countryLease;CountryClient.Source oldSource=leaseSource;
        boolean same=binding.equals(countryBinding);
        int action=old==null?2:RustCore.leaseAction(SystemClock.elapsedRealtime(),old.deadline,same);
        if(action==2){
            retireCountry();old=null;oldSource=null;
            engine.submit(()->{if(!gate.accepts(token))return;stopPayload();try{ensureTun(NetworkConfig.mtu(settings));}catch(Exception e){throw new IllegalStateException(e);}}).get(15,TimeUnit.SECONDS);
        }
        if(!gate.accepts(token))return;
        if(!upstreamAvailable())throw new IllegalStateException("Country control channel offline");
        if(action!=0){
            CountryClient.Source source=new CountryClient.Source(settings);CountryClient client=new CountryClient(source);countryFetcher=client;
            CountryClient.Lease next;
            try{next=client.acquire(country,SystemClock.elapsedRealtime());}finally{countryFetcher=null;}
            boolean selected=false;try{selected=binding.equals(CountryClient.binding(store.load()));}catch(Exception ignored){}
            if(!gate.accepts(token)||!selected||RustCore.leaseAction(SystemClock.elapsedRealtime(),next.deadline,true)==2){retire(next,source);return;}
            try{
                initializeNative(token);
                Profile candidate=Profile.parse(next.uri);
                if(!install(candidate,settings,token)){retire(next,source);return;}
                synchronized(gate){
                    if(!gate.accepts(token)){retire(next,source);return;}
                    countryBinding=binding;leaseSource=source;countryLease=next;lastHealth=0;
                    watchLease(next,token);
                }
                retire(old,oldSource);
            }catch(Exception error){retire(next,source);throw error;}
        }
        if(!gate.accepts(token))return;
        if(countryLease!=null&&(!coreRunning||!installedOptions.equals(NetworkConfig.identity(settings)))){
            initializeNative(token);if(!install(Profile.parse(countryLease.uri),settings,token))return;
        }
        long delay=status.latency;
        if(CheckPolicy.healthDue(SystemClock.elapsedRealtime(),lastHealth,failures>0||checkEpoch.get()!=healthyEpoch,true)||delay<0){delay=activeProbe(token);lastHealth=SystemClock.elapsedRealtime();healthyEpoch=checkEpoch.get();}
        failures=0;publish(token,"Connected",country+" · authenticated country route",delay,15);
    }
    private void check(long token){
        if(!gate.accepts(token)||!checking.compareAndSet(false,true))return;
        int interval=60;long epoch=checkEpoch.get(),began=SystemClock.elapsedRealtime();
        try{
            JSONObject routeSettings=store.load();
            if(!routeSettings.optString("country","").isEmpty()){interval=15;checkCountry(routeSettings,token);return;}
            if(countryLease!=null||!countryBinding.isEmpty())retireCountry();
            if(!upstreamAvailable()){
                interval=CheckPolicy.offlineSeconds();publish(token,"Waiting for network",tunOpen?"VPN routes retained; waiting for the default network":"No default network; waiting to open VPN",-1,interval);return;
            }
            JSONObject settings=store.load();boolean interactive=getSystemService(PowerManager.class).isInteractive();
            String manual=SettingsStore.manual(settings),source=settings.optString("source",SubscriptionClient.DEFAULT);
            interval=CheckPolicy.nextSeconds(manual!=null,settings.optInt("interval",60),interactive);
            String content=manual;boolean cached=false,updateUnavailable=false;
            if(manual==null){
                SubscriptionClient client=new SubscriptionClient();fetcher=client;
                try{content=client.fetch(source);}catch(Exception error){
                    if(!gate.accepts(token))return;
                    if(active!=null&&coreRunning)updateUnavailable=true;
                    else{content=store.cache(source);if(content.isEmpty())throw error;cached=true;}
                }finally{fetcher=null;}
            }
            if(!gate.accepts(token))return;
            Profile candidate=updateUnavailable?active:Profile.subscription(content);
            boolean same=active!=null&&active.key().equals(candidate.key());
            boolean optionsChanged=!installedOptions.equals(NetworkConfig.identity(settings));
            boolean healthDue=CheckPolicy.healthDue(SystemClock.elapsedRealtime(),lastHealth,epoch!=healthyEpoch||failures>0,interactive);
            if(same&&coreRunning&&!optionsChanged&&!healthDue){
                publish(token,"Connected",updateUnavailable?"Subscription unavailable; retaining active VPN (check pending)":candidate.protocolLabel()+" · "+candidate.transportLabel(),status.latency,interval);return;
            }
            initializeNative(token);if(!gate.accepts(token))return;
            long latency=-1;boolean replacing=active!=null&&!same;
            if(replacing){publish(token,"Checking update","Testing candidate before replacing active VPN",status.latency,interval);latency=candidateProbe(candidate,token);}
            // Endpoint-check failures alone must not kill otherwise-working sessions.
            if(!same||!coreRunning||optionsChanged){
                publish(token,"Connecting",replacing?"Installing verified update":"Opening VPN; reachability check follows",latency,interval);
                if(!install(candidate,settings,token))return;
            }
            if(latency<0)latency=activeProbe(token);
            if(!gate.accepts(token))return;
            if(manual==null&&!cached&&!updateUnavailable)store.cache(source,content);
            failures=0;lastHealth=SystemClock.elapsedRealtime();healthyEpoch=epoch;Diagnostics.success(lastHealth-began);
            publish(token,"Connected",cached||updateUnavailable?"Subscription unavailable; active endpoint check passed":candidate.protocolLabel()+" · "+candidate.transportLabel(),latency,interval);
        }catch(Exception error){
            if(!gate.accepts(token))return;
            Diagnostics.failure(error);failures++;interval=RotationPolicy.retrySeconds(failures);
            if(!store.load().optString("country","").isEmpty()){
                interval=Math.min(interval,15);
                publish(token,"Country unavailable",coreRunning?"Country renewal failed; no default fallback":"Country traffic blocked; retrying without default fallback",-1,interval);
            }else publish(token,coreRunning?"Checking connection":"Reconnecting",error instanceof IllegalArgumentException?"Invalid profile rejected; no update installed":"Reachability check failed; VPN retained and retry scheduled",-1,interval);
        }catch(LinkageError error){main.post(()->{if(gate.accepts(token)){event("Native engine unavailable on this device");disconnect(true);}});
        }finally{
            checking.set(false);final int seconds=interval;
            main.post(()->{if(stopping||destroyed||!gate.active())return;boolean pending=refreshPending||!gate.accepts(token);refreshPending=false;requestCheck(pending?0:seconds*1000L);});
        }
    }
    private void disconnect(boolean user){
        if(user){try{store.pause();}catch(Exception ignored){event("Could not save pause preference");}}
        gate.stop();retireCountry();CountryClient route=countryFetcher;if(route!=null)new Thread(route::cancel,"cancel-country-request").start();
        refreshPending=false;if(scheduled!=null)scheduled.cancel(true);if(stopping)return;stopping=true;
        status=new VpnStatus("Disconnecting","Closing VPN resources",status.host,status.protocol,status.transport,-1,0,0,true,tunOpen,coreRunning);broadcast();
        SubscriptionClient client=fetcher;if(client!=null)new Thread(client::cancel,"cancel-subscription").start();
        Runnable watchdog=()->{if(!stopping)return;getSystemService(NotificationManager.class).cancel(1);stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();android.os.Process.killProcess(android.os.Process.myPid());};
        main.postDelayed(watchdog,2500);
        engine.execute(()->{shutdownEngine();main.post(()->{
            main.removeCallbacks(watchdog);stopping=false;connectedAt=0;active=null;status=VpnStatus.offline();event("Disconnected; explicit Connect is required to resume");broadcast();
            stopForeground(STOP_FOREGROUND_REMOVE);getSystemService(NotificationManager.class).cancel(1);stopSelf();
        });});
    }
    private void shutdownEngine(){
        try{if(tun!=null)tun.close();}catch(Exception ignored){}tun=null;tunOpen=false;
        try{if(core!=null)core.stopLoop();}catch(Exception ignored){}core=null;coreRunning=false;nativeConfig="";installedOptions="";
    }
    @Override public void onRevoke(){disconnect(true);}
    @Override public void onDestroy(){
        destroyed=true;gate.stop();retireCountry();leaseCleanup.shutdown();CountryClient route=countryFetcher;if(route!=null)new Thread(route::cancel,"cancel-country-request").start();if(scheduled!=null)scheduled.cancel(true);
        try{connectivity.unregisterNetworkCallback(networkCallback);}catch(Exception ignored){}
        observers.clear();if(!stopping)engine.execute(this::shutdownEngine);io.shutdownNow();engine.shutdown();super.onDestroy();
    }
}
