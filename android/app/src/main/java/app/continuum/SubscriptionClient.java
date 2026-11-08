package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

public final class SubscriptionClient {
    public static final String DEFAULT="https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt";
    private volatile HttpsURLConnection current;
    private volatile boolean cancelled;
    public void cancel(){cancelled=true;HttpsURLConnection c=current;if(c!=null)c.disconnect();}
    public static String validate(String value) {
        URI uri=URI.create(value.trim());
        if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getFragment()!=null)
            throw new IllegalArgumentException("Use an HTTPS subscription URL without credentials");
        return uri.toString();
    }
    public String fetch(String source) throws IOException {
        String url=validate(source);long deadline=System.nanoTime()+20_000_000_000L;
        for(int redirect=0;redirect<5;redirect++){
            check(deadline);
            HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();current=c;
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(5000);c.setReadTimeout(5000);
            c.setUseCaches(false);c.setRequestProperty("Cache-Control","no-cache");c.setRequestProperty("User-Agent","Continuum/0.2");
            try {
                check(deadline);int code=c.getResponseCode();
                if(code==301||code==302||code==303||code==307||code==308){
                    String location=c.getHeaderField("Location");if(location==null)throw new IOException("Missing redirect");
                    url=validate(new URL(new URL(url),location).toString());continue;
                }
                if(code!=200)throw new IOException("Subscription unavailable");
                ByteArrayOutputStream out=new ByteArrayOutputStream();
                try(InputStream in=c.getInputStream()){
                    byte[] buffer=new byte[4096];int n;
                    while((n=in.read(buffer))!=-1){check(deadline);if(out.size()+n>65536)throw new IOException("Subscription too large");out.write(buffer,0,n);}
                }
                check(deadline);return out.toString(StandardCharsets.UTF_8.name());
            } finally {current=null;c.disconnect();}
        }
        throw new IOException("Too many redirects");
    }
    private void check(long deadline)throws InterruptedIOException{
        if(cancelled||Thread.currentThread().isInterrupted()||System.nanoTime()>deadline)throw new InterruptedIOException("Subscription check cancelled or timed out");
    }
}
