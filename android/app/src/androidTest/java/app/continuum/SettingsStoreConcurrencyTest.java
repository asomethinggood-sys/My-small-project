package app.continuum;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class SettingsStoreConcurrencyTest {
    @Test public void readerNeverDeletesPendingAtomicWrite()throws Exception{
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        SettingsStore store=new SettingsStore(context);JSONObject previous=store.load();
        File pending=new File(context.getFilesDir(),"settings-v2.json.new");
        try{
            store.save(new JSONObject().put("country","DE"));
            try(FileOutputStream out=new FileOutputStream(pending)){out.write("{\"country\":\"FR\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8));}
            assertEquals("DE",store.load().getString("country"));
            assertTrue("A reader must not delete the concurrent writer's pending file",pending.isFile());
            assertTrue(pending.renameTo(new File(context.getFilesDir(),"settings-v2.json")));
            assertEquals("FR",store.load().getString("country"));
        }finally{pending.delete();store.save(previous);}
    }
}
