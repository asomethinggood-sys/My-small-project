package app.continuum.probe;

import android.app.Activity;
import android.os.Bundle;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Test-only separate UID. 198.18.0.42 is reachable only via the fixture proxy's redirect. */
public final class ProbeActivity extends Activity {
    @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(()->{
        String result="FAIL";
        try {
            HttpURLConnection c=(HttpURLConnection)new URL("http://198.18.0.42/marker").openConnection();
            c.setConnectTimeout(7000);c.setReadTimeout(7000);
            try(InputStream in=c.getInputStream()){
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] data=new byte[256];int n;
                while((n=in.read(data))!=-1){if(out.size()>1024)throw new IOException();out.write(data,0,n);}
                if(c.getResponseCode()==200&&"continuum-vpn-path-ok".equals(out.toString("UTF-8")))result="PASS";
            } finally {c.disconnect();}
        }catch(Exception ignored){}
        try(FileOutputStream out=openFileOutput("result",MODE_PRIVATE)){out.write(result.getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}
        runOnUiThread(this::finish);
    },"test-network-request").start();}
}
