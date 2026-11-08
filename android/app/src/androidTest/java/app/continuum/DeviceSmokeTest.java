package app.continuum;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
import libv2ray.*;
import go.Seq;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class DeviceSmokeTest {
    @Test public void nativeEngineLoadsAndStartsValidatedOutboundOnAndroid() throws Exception {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        Seq.setContext(context);
        Libv2ray.initCoreEnv(context.getFilesDir().getAbsolutePath(),"");
        assertTrue(Libv2ray.checkVersionX().contains("26.10.31"));
        CoreController core=Libv2ray.newCoreController(new CoreCallbackHandler(){
            public long startup(){return 0;}
            public long shutdown(){return 0;}
            public long onEmitStatus(long code,String text){return 0;}
        });
        Profile profile=Profile.parse("vless://123e4567-e89b-12d3-a456-426614174000@test.example.com:443?encryption=none&security=tls&type=ws&path=%2Ftest");
        try {
            // Outbound-only: exercises the packaged JNI engine without claiming a VPN/Internet test.
            core.startLoop(profile.config(false).toString(),0);
            assertTrue(core.getIsRunning());
        } finally { core.stopLoop(); }
        assertFalse(core.getIsRunning());
    }
    @Test public void nativeScreenLaunchesOfflineAndCapturesScreenshot() throws Exception {
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        var context=instrumentation.getTargetContext();
        Activity screen=instrumentation.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try {
            instrumentation.waitForIdleSync();
            assertFalse(TunnelService.snapshot.running);
            Bitmap bitmap=instrumentation.getUiAutomation().takeScreenshot();
            assertNotNull(bitmap);
            File file=new File(context.getExternalFilesDir(null),"continuum-screen.png");
            try(FileOutputStream out=new FileOutputStream(file)){assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,out));}
            // Gradle uninstalls the target after connected tests, removing app-scoped files.
            // Capture a shell-owned copy in Downloads before finishing the Activity.
            for(String command:new String[]{"mkdir -p /sdcard/Download", "screencap -p /sdcard/Download/continuum-screen.png"}) {
                try(var output=new android.os.ParcelFileDescriptor.AutoCloseInputStream(
                    instrumentation.getUiAutomation().executeShellCommand(command))) {
                    byte[] buffer=new byte[1024]; while(output.read(buffer)!=-1) { /* wait for command */ }
                }
            }
        } finally { instrumentation.runOnMainSync(screen::finish); }
    }
}
