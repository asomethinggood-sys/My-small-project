package app.continuum;

import android.app.Activity;
import android.content.Intent;
import android.view.*;
import android.widget.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static org.junit.Assume.*;

@RunWith(AndroidJUnit4.class)
public class BetaUiTest {
    @Test public void betaHomeOffersServerListWithoutSourceControls(){
        assumeTrue(BuildConfig.BETA_POOL);
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();
        Activity activity=inst.startActivitySync(new Intent(inst.getTargetContext(),ContinuumActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{inst.runOnMainSync(()->{
            View servers=activity.findViewById(android.R.id.content).findViewWithTag("servers");
            assertNotNull(servers);assertTrue(servers.isEnabled());
            audit(activity.findViewById(android.R.id.content));
            // Opening the list must not connect or automatically run network probes.
            assertTrue(servers.performClick());
        });inst.waitForIdleSync();}finally{inst.runOnMainSync(activity::finish);}
    }
    private void audit(View view){
        assertFalse(view instanceof EditText);
        if(view instanceof TextView){String text=((TextView)view).getText().toString().toLowerCase(java.util.Locale.ROOT);for(String bad:new String[]{"github","repository","subscription","xray","https://","vless"})assertFalse(text.contains(bad));}
        if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)audit(group.getChildAt(i));}
    }
}
