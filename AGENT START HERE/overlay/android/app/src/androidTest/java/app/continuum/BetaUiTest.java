package app.continuum;

import android.app.*;
import android.content.Intent;
import android.view.*;
import android.widget.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;
import static org.junit.Assume.*;

@RunWith(AndroidJUnit4.class)
public class BetaUiTest {
    @Test public void betaHomeAndTenSlotDialogExposeOnlyProductCopy(){
        assumeTrue(BuildConfig.BETA_POOL);
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();
        Activity activity=inst.startActivitySync(new Intent(inst.getTargetContext(),ContinuumActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        AlertDialog[] dialog={null};AtomicBoolean connected=new AtomicBoolean();
        try{inst.runOnMainSync(()->{
            View servers=activity.findViewById(android.R.id.content).findViewWithTag("servers");
            assertNotNull(servers);assertTrue(servers.isEnabled());
            audit(activity.findViewById(android.R.id.content),new ArrayList<>());
            dialog[0]=BetaServerDialog.show(activity,new SettingsStore(activity),()->connected.set(true));
            List<String> strings=new ArrayList<>();audit(dialog[0].getWindow().getDecorView(),strings);
            for(int slot=1;slot<=10;slot++)assertEquals(1,Collections.frequency(strings,BetaCatalog.label(slot)));
            assertEquals(10,Collections.frequency(strings,"Not checked"));
            assertEquals(10,Collections.frequency(strings,"Connect"));
            assertTrue(strings.contains("Check all servers"));
            assertTrue(strings.contains("Automatic · best measured server"));
            assertFalse("Opening the dialog must not connect",connected.get());
        });inst.waitForIdleSync();}finally{inst.runOnMainSync(()->{if(dialog[0]!=null)dialog[0].dismiss();activity.finish();});}
    }
    private void audit(View view,List<String> strings){
        assertFalse(view instanceof EditText);
        if(view instanceof TextView){String raw=((TextView)view).getText().toString();strings.add(raw);String text=raw.toLowerCase(java.util.Locale.ROOT);for(String bad:new String[]{"github","repository","subscription","xray","https://","vless"})assertFalse(text.contains(bad));}
        if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)audit(group.getChildAt(i),strings);}
    }
}
