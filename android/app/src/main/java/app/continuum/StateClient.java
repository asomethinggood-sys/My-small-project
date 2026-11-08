package app.continuum;

import android.content.*;
import android.os.*;

/** UI observes the isolated VPN process through Binder, never static cross-process fields. */
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
        public void onServiceConnected(ComponentName name,IBinder binder){service=new Messenger(binder);request();}
        public void onServiceDisconnected(ComponentName name){service=null;status=VpnStatus.offline();unbind();}
        public void onBindingDied(ComponentName name){onServiceDisconnected(name);}
    };
    private final Runnable poll=new Runnable(){public void run(){if(!observing)return;if(!bound){bound=context.bindService(new Intent(context,TunnelService.class).setAction(TunnelService.OBSERVE),connection,0);}else request();handler.postDelayed(this,1000);}};
    public StateClient(Context context){this.context=context;}
    public void begin(){if(observing)return;observing=true;handler.post(poll);}
    public void end(){observing=false;handler.removeCallbacks(poll);unbind();}
    private void unbind(){if(bound){try{context.unbindService(connection);}catch(IllegalArgumentException ignored){}bound=false;}service=null;}
    private void request(){if(service==null)return;Message m=Message.obtain(null,TunnelService.STATE);m.replyTo=inbox;try{service.send(m);}catch(RemoteException e){unbind();}}
    public void connect(){new SettingsStore(context).resumeExplicitly();status=new VpnStatus("Connecting","Starting VPN service","Waiting for endpoint",status.protocol,status.transport,-1,0,0,true,false,false);context.startForegroundService(new Intent(context,TunnelService.class).setAction(TunnelService.START));}
    public void disconnect(){new SettingsStore(context).pause();context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.STOP));}
    public void refresh(){if(status.running)context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.REFRESH));}
}
