package app.continuum;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static org.junit.Assume.*;

@RunWith(AndroidJUnit4.class)
public class ContinuumUiTest {
    private void shell(Instrumentation inst,String cmd)throws Exception{
        try(java.io.InputStream in=new ParcelFileDescriptor.AutoCloseInputStream(inst.getUiAutomation().executeShellCommand(cmd))){byte[] b=new byte[1024];while(in.read(b)!=-1){}}
    }
    private void check(AccessibilityNodeInfo node){
        assertNotNull(node);String text=(String.valueOf(node.getText())+" "+String.valueOf(node.getContentDescription())).toLowerCase(java.util.Locale.ROOT);
        for(String bad:new String[]{"github","asomethinggood","repository","subscription","import profile","custom config","xray","vless","websocket","https://","http://","private.example"})assertFalse("UI exposed "+bad,text.contains(bad));
        assertFalse("Configuration input must not be present",String.valueOf(node.getClassName()).contains("EditText"));
        for(int i=0;i<node.getChildCount();i++){AccessibilityNodeInfo child=node.getChild(i);if(child!=null){check(child);child.recycle();}}
    }
    private void snapshot(Instrumentation inst,Activity screen,String name)throws Exception{
        inst.waitForIdleSync();long until=SystemClock.elapsedRealtime()+8000;boolean[] focus={false};
        while(SystemClock.elapsedRealtime()<until){inst.runOnMainSync(()->focus[0]=screen.getWindow().getDecorView().hasWindowFocus());if(focus[0])break;Thread.sleep(100);}
        assertTrue("App must be visible",focus[0]);Thread.sleep(400);
        check(inst.getUiAutomation().getRootInActiveWindow());
        shell(inst,"screencap -p /sdcard/Download/continuum-"+name+".png");
    }
    @Test public void consumerHomeSettingsAndPrivacyHaveNoConfigurationSurface()throws Exception{
        assumeTrue(BuildConfig.MANAGED_UI);
        Instrumentation inst=InstrumentationRegistry.getInstrumentation();Context context=inst.getTargetContext();
        shell(inst,"am force-stop com.google.android.apps.nexuslauncher");
        Activity activity=inst.startActivitySync(new Intent(context,ContinuumActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{
            snapshot(inst,activity,"home");
            inst.runOnMainSync(()->activity.findViewById(android.R.id.content).findViewWithTag("settings").performClick());
            Thread.sleep(400);check(inst.getUiAutomation().getRootInActiveWindow());
            shell(inst,"screencap -p /sdcard/Download/continuum-settings.png");
            inst.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);inst.waitForIdleSync();
            inst.runOnMainSync(()->activity.findViewById(android.R.id.content).findViewWithTag("privacy").performClick());
            Thread.sleep(400);check(inst.getUiAutomation().getRootInActiveWindow());
            inst.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
            // Inject a hostile/detail-rich backend status: rendering must still
            // use only product copy, never the raw service strings.
            inst.runOnMainSync(()->{try{
                java.lang.reflect.Field field=ContinuumActivity.class.getDeclaredField("client");field.setAccessible(true);
                StateClient client=(StateClient)field.get(activity);
                client.status=new VpnStatus("Connected","https://github.com/asomethinggood-sys/private","private.example","XRAY","WebSocket",52,0,SystemClock.elapsedRealtime(),true,true,true);
                java.lang.reflect.Method render=ContinuumActivity.class.getDeclaredMethod("render");render.setAccessible(true);render.invoke(activity);
            }catch(Exception e){throw new AssertionError(e);}});
            Thread.sleep(250);check(inst.getUiAutomation().getRootInActiveWindow());
        }finally{inst.runOnMainSync(activity::finish);}
    }
}
