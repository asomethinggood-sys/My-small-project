package app.continuum;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.view.View;
import android.widget.EditText;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class NyxUiTest {
    private void shell(android.app.Instrumentation inst,String command)throws Exception{
        try(java.io.InputStream in=new ParcelFileDescriptor.AutoCloseInputStream(inst.getUiAutomation().executeShellCommand(command))){byte[] b=new byte[1024];while(in.read(b)!=-1){}}
    }
    private void removeLauncherOverlay(android.app.Instrumentation inst)throws Exception{
        // The API35 emulator's Pixel Launcher can ANR under KVM load. Do not hide
        // application error dialogs globally: stop only that unrelated launcher.
        shell(inst,"am force-stop com.google.android.apps.nexuslauncher");
    }
    private void snapshot(android.app.Instrumentation inst,Activity screen,String name)throws Exception{
        inst.waitForIdleSync();long deadline=SystemClock.elapsedRealtime()+8000;boolean[] focused={false};
        while(SystemClock.elapsedRealtime()<deadline){
            inst.runOnMainSync(()->focused[0]=screen.getWindow().getDecorView().hasWindowFocus());
            if(focused[0])break;Thread.sleep(100);
        }
        assertTrue("Nyx must have focus; do not publish screenshots under a system error dialog",focused[0]);
        Thread.sleep(600);shell(inst,"screencap -p /sdcard/Download/nyx-"+name+".png");
    }
    @Test public void locationsAreReadOnlyAndSearchWorks()throws Exception{
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();Context context=inst.getTargetContext();
        String before=new SettingsStore(context).load().toString();
        Activity screen=inst.startActivitySync(new Intent(context,LocationsActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{
            inst.runOnMainSync(()->{
                View root=screen.findViewById(android.R.id.content);
                assertNotNull(root.findViewWithTag("country-DE"));
                EditText search=root.findViewWithTag("country-search");search.setText("DE");
                assertNotNull(root.findViewWithTag("country-DE"));assertNull(root.findViewWithTag("country-FR"));
                search.setText("zzzzzz");assertNull(root.findViewWithTag("country-DE"));
            });
            assertEquals(before,new SettingsStore(context).load().toString());
        }finally{inst.runOnMainSync(screen::finish);}
    }
    @Test public void designSnapshots()throws Exception{
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();Context context=inst.getTargetContext();
        removeLauncherOverlay(inst);
        SettingsStore settings=new SettingsStore(context);settings.save(settings.load().put("selection",-1).put("source",SubscriptionClient.DEFAULT));
        Activity screen=inst.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{snapshot(inst,screen,"home");}finally{inst.runOnMainSync(screen::finish);}
        removeLauncherOverlay(inst);
        Activity locations=inst.startActivitySync(new Intent(context,LocationsActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{snapshot(inst,locations,"locations");}finally{inst.runOnMainSync(locations::finish);}
    }
    @Test public void customOrbitHandlesEveryPhaseAndReducedMotion()throws Exception{
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();Context context=inst.getTargetContext();
        Activity screen=inst.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{inst.runOnMainSync(()->{
            NyxOrbit orbit=new NyxOrbit(screen);screen.setContentView(orbit);
            for(int phase=0;phase<4;phase++){orbit.phase(phase);assertNotNull(orbit.getContentDescription());}
            assertEquals(1000,RustCore.motionProgress(0,420,true));
        });}finally{inst.runOnMainSync(screen::finish);}
    }
}
