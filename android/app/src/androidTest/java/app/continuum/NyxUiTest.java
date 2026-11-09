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
    @Test public void locationsAreReadOnlyAndSearchWorks()throws Exception{
        android.app.Instrumentation inst=InstrumentationRegistry.getInstrumentation();Context context=inst.getTargetContext();
        String before=new SettingsStore(context).load().toString();
        Activity screen=inst.startActivitySync(new Intent(context,LocationsActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try{
            inst.runOnMainSync(()->{
                View root=screen.findViewById(android.R.id.content);
                assertNotNull(root.findViewWithTag("country-DE"));
                EditText search=root.findViewWithTag("country-search");search.setText("Germany");
                assertNotNull(root.findViewWithTag("country-DE"));assertNull(root.findViewWithTag("country-FR"));
                search.setText("zzzzzz");assertNull(root.findViewWithTag("country-DE"));
            });
            assertEquals(before,new SettingsStore(context).load().toString());
        }finally{inst.runOnMainSync(screen::finish);}
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
