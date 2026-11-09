package app.continuum;

import android.app.Activity;
import android.content.*;
import android.net.*;
import android.os.*;
import android.widget.TextView;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.util.function.BooleanSupplier;
import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class DeviceSmokeTest {
    private final android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();
    private final Context context=inst.getTargetContext();
    private StateClient observer;
    private String shell(String command)throws Exception{
        try(InputStream in=new ParcelFileDescriptor.AutoCloseInputStream(inst.getUiAutomation().executeShellCommand(command))){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[2048];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toString("UTF-8");
        }
    }
    private void await(String description,BooleanSupplier condition,long seconds)throws Exception{
        long deadline=SystemClock.elapsedRealtime()+seconds*1000;
        while(!condition.getAsBoolean()&&SystemClock.elapsedRealtime()<deadline)Thread.sleep(100);
        if(!condition.getAsBoolean()){
            VpnStatus s=observer==null?VpnStatus.offline():observer.status;
            fail(description+"; state="+s.state+" running="+s.running+" tun="+s.tunOpen+" engine="+s.engineRunning+" androidVpn="+vpn()+"\n"+(observer==null?"":observer.history)+"\n"+shell("dumpsys activity services "+context.getPackageName()));
        }
    }
    private boolean vpn(){
        ConnectivityManager cm=context.getSystemService(ConnectivityManager.class);
        for(Network n:cm.getAllNetworks()){NetworkCapabilities c=cm.getNetworkCapabilities(n);if(c!=null&&c.hasTransport(NetworkCapabilities.TRANSPORT_VPN))return true;}return false;
    }
    private Activity launch(){return inst.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));}
    private void press(Activity screen,String text)throws Exception{
        await("button should show "+text,()->{final boolean[] found={false};inst.runOnMainSync(()->{TextView v=screen.findViewById(android.R.id.content).findViewWithTag("connect");found[0]=text.contentEquals(v.getText())&&v.isEnabled();});return found[0];},8);
        inst.runOnMainSync(()->screen.findViewById(android.R.id.content).findViewWithTag("connect").performClick());
    }
    private void cleanup()throws Exception{
        context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.STOP));
        long deadline=SystemClock.elapsedRealtime()+6000;Thread.sleep(300);
        while((observer.status.running||vpn())&&SystemClock.elapsedRealtime()<deadline)Thread.sleep(100);
        inst.runOnMainSync(observer::end);
    }
    @Test public void realTunDnsWebsitesLargeTransfersUdpAndDisconnect()throws Exception{
        shell("appops set app.nyx.vpn ACTIVATE_VPN allow");shell("pm grant app.nyx.vpn android.permission.POST_NOTIFICATIONS");
        JSONArray profiles=new JSONArray(shell("cat /sdcard/Download/continuum-fixtures.json"));
        SettingsStore store=new SettingsStore(context);observer=new StateClient(context);inst.runOnMainSync(observer::begin);
        try{
            for(int i=0;i<profiles.length();i++){
                int mtu=new int[]{1280,1400,1500,1400}[i];
                store.save(store.load().put("selection",0).put("dualStack",false).put("mtu",mtu).put("profiles",new JSONArray().put(new JSONObject().put("uri",profiles.getString(i)))));
                Activity screen=launch();long started=SystemClock.elapsedRealtime();press(screen,"Connect");
                await("real engine and TUN connect for fixture "+i,()->observer.status.engineRunning&&observer.status.tunOpen&&"Connected".equals(observer.status.state),100);
                assertTrue("Android VPN network exists",vpn());
                android.util.Log.i("ContinuumProbe","Fixture "+i+" MTU "+mtu+" Connected after "+(SystemClock.elapsedRealtime()-started)+" ms (runner, not Tehran)");
                shell("run-as app.continuum.probe rm -f files/result files/report");shell("am start -W -n app.continuum.probe/.ProbeActivity");
                String result="";long deadline=SystemClock.elapsedRealtime()+120000;
                while(SystemClock.elapsedRealtime()<deadline){result=shell("run-as app.continuum.probe cat files/result").trim();if(result.equals("PASS")||result.equals("FAIL"))break;Thread.sleep(250);}
                String report=shell("run-as app.continuum.probe cat files/report");android.util.Log.i("ContinuumProbe","Fixture "+i+"\n"+report);
                assertEquals("Separate UID website regression suite, fixture "+i+"\n"+report,"PASS",result);
                screen=launch();long previousNext=observer.status.nextCheck;
                context.startService(new Intent(context,TunnelService.class).setAction(TunnelService.REFRESH));
                await("Check now bypasses five-minute health cache",()->observer.status.nextCheck!=previousNext&&"Connected".equals(observer.status.state),40);
                press(screen,"Disconnect");await("Disconnect closes resources while observer remains bound",()->!observer.status.running&&!observer.status.tunOpen&&!observer.status.engineRunning&&!vpn(),6);
                assertTrue(store.paused());context.startService(new Intent(context,TunnelService.class).setAction(VpnService.SERVICE_INTERFACE));
                Thread.sleep(1500);assertFalse(vpn());assertFalse(observer.status.running);inst.runOnMainSync(screen::finish);
            }
        }finally{cleanup();}
    }
    @Test public void disconnectDuringBlockedFetchThenReconnect()throws Exception{
        shell("appops set app.nyx.vpn ACTIVATE_VPN allow");shell("pm grant app.nyx.vpn android.permission.POST_NOTIFICATIONS");
        SettingsStore store=new SettingsStore(context);store.save(store.load().put("selection",-1).put("source","https://10.255.255.1/stalled"));
        observer=new StateClient(context);inst.runOnMainSync(observer::begin);Activity screen=launch();
        try{
            press(screen,"Connect");await("connecting",()->observer.status.running,10);press(screen,"Disconnect");
            await("stop independent of blocked HTTPS",()->!observer.status.running&&!vpn(),6);
            JSONArray fixtures=new JSONArray(shell("cat /sdcard/Download/continuum-fixtures.json"));
            store.save(store.load().put("selection",0).put("profiles",new JSONArray().put(new JSONObject().put("uri",fixtures.getString(0)))));
            press(screen,"Connect");await("new generation runs after stale fetch",()->observer.status.engineRunning&&observer.status.tunOpen,60);
            press(screen,"Disconnect");await("second stop",()->!observer.status.running&&!vpn(),6);
            Thread.sleep(6000);assertFalse("stale work cannot resurrect stopped VPN",vpn());assertTrue(store.paused());
            shell("screencap -p /sdcard/Download/continuum-screen.png");
        }finally{cleanup();inst.runOnMainSync(screen::finish);}
    }
}
