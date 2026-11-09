package app.continuum;

import android.content.*;
import android.os.*;

/** Visible UI subscribes to changes. No per-second Binder requests or background UI work. */
public final class StateClient {
    public volatile VpnStatus status=VpnStatus.offline();
    public volatile String history="";
    private final Context context;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private boolean observing,bound;
    private Messenger service;
    private final Messenger inbox=new Messenger(new Handler(Looper.getMainLooper(),message->{
        if(message.what==TunnelService.STATE){status=VpnStatus.from(message.getData());history=message.getData().getString("history","");}
        return true;
    }));
    private final ServiceConnection connection=new ServiceConnection(){
        public void onServiceConnected(ComponentName name,IBinder binder){service=new Messenger(binder);request(TunnelService.STATE);}
        public void onServiceDisconnected(ComponentName name){status=VpnStatus.offline();unbind();if(observing){handler.removeCallbacks(rebind);handler.postDelayed(rebind,500);}}
        public void onBindingDied(ComponentName name){onServiceDisconnected(name);}
    };
    private final Runnable rebind=new Runnable(){public void run(){
        if(!observing)return;
        if(!bound)bound=context.bindService(new Intent(context,TunnelService.class).setAction(TunnelService.OBSERVE),connection,0);
        if(!bound)handler.postDelayed(this,2000);
    }};
    public StateClient(Context context){this.context=context;}
    public void begin(){if(observing)return;observing=true;handler.post(rebind);}
    public void end(){observing=false;handler.removeCallbacks(rebind);request(TunnelService.UNOBSERVE);unbind();}
    private void unbind(){if(bound){try{context.unbindService(connection);}catch(IllegalArgumentException ignored){}bound=false;}service=null;}
    private void request(int what){if(service==null)return;Message m=Message.obtain(null,what);m.replyTo=inbox;try{service.send(m);}catch(RemoteException e){unbind();if(observing)handler.postDelayed(rebind,500);}}
    public void connect(){
        status=new VpnStatus("Connecting","Starting VPN service","Waiting for endpoint",status.protocol,status.transport,-1,0,0,true,false,false);
        context.startForegroundService(new Intent(context,TunnelService.class).setAction(TunnelService.START));
        if(observing){handler.removeCallbacks(rebind);handler.postDelayed(rebind,100);}
    }
    public void disconnect(){
        new SettingsStore(context).pause();
        status=new VpnStatus("Disconnecting","Closing VPN resources",status.host,status.protocol,status.transport,-1,0,0,true,status.tunOpen,status.engineRunning);
        context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.STOP));
    }
    public void refresh(){if(status.running)context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.REFRESH));}
}
