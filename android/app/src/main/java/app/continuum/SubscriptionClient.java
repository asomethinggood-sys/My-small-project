package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.net.ssl.HttpsURLConnection;

/** Android HTTPS adapter; Rust decides validator eligibility and failure backoff. */
public final class SubscriptionClient {
    public static final String DEFAULT="https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt";
    private static final Map<String,Entry> CACHE=new LinkedHashMap<>();
    private static long forcedGeneration;
    private static final class Entry {
        String resource="",body="",etag="",modified="";
        int failures;volatile long nextAttempt;
    }
    private volatile HttpsURLConnection current;
    private volatile boolean cancelled;
    public void cancel(){cancelled=true;HttpsURLConnection c=current;if(c!=null)c.disconnect();}
    public static synchronized void forceNext(){forcedGeneration++;for(Entry entry:CACHE.values())entry.nextAttempt=0;}
    private static synchronized long generation(){return forcedGeneration;}
    private static synchronized void failed(Entry entry,long generation){
        // An old in-flight request must not overwrite a newer manual/network retry.
        if(generation!=forcedGeneration)return;
        entry.failures=Math.min(entry.failures+1,30);
        entry.nextAttempt=System.nanoTime()+RustCore.fetchBackoff(entry.failures,60)*1_000_000_000L;
    }
    private static synchronized Entry entry(String source){
        Entry value=CACHE.get(source);
        if(value==null){if(CACHE.size()>=4)CACHE.remove(CACHE.keySet().iterator().next());value=new Entry();CACHE.put(source,value);}return value;
    }
    public static String validate(String value){
        URI uri=URI.create(value.trim());
        if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getFragment()!=null)throw new IllegalArgumentException("Use an HTTPS subscription URL without credentials");
        return uri.toString();
    }
    public String fetch(String source)throws IOException{
        String origin=validate(source),url=origin;Entry cache=entry(origin);long generation=generation();
        if(System.nanoTime()<cache.nextAttempt)throw new IOException("Subscription retry deferred");
        long deadline=System.nanoTime()+20_000_000_000L;
        try{
            for(int redirect=0;redirect<5;redirect++){
                check(deadline);HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();current=c;
                c.setInstanceFollowRedirects(false);c.setConnectTimeout(5000);c.setReadTimeout(5000);
                c.setUseCaches(false);c.setRequestProperty("Cache-Control","no-cache");c.setRequestProperty("User-Agent","Continuum/0.4");
                boolean conditional=RustCore.reuseValidator(true,url.equals(cache.resource),!cache.body.isEmpty())&&(!cache.etag.isEmpty()||!cache.modified.isEmpty());
                if(conditional){if(!cache.etag.isEmpty())c.setRequestProperty("If-None-Match",cache.etag);else c.setRequestProperty("If-Modified-Since",cache.modified);}
                try{
                    check(deadline);int code=c.getResponseCode();
                    if(code==301||code==302||code==303||code==307||code==308){
                        String location=c.getHeaderField("Location");if(location==null)throw new IOException("Missing redirect");url=validate(new URL(new URL(url),location).toString());continue;
                    }
                    if(code==304){
                        if(!conditional)throw new IOException("Unsolicited not-modified response");
                        check(deadline);cache.failures=0;cache.nextAttempt=0;RustCore.addMetric(3,1);return cache.body;
                    }
                    if(code!=200)throw new IOException("Subscription unavailable");
                    ByteArrayOutputStream out=new ByteArrayOutputStream();
                    try(InputStream in=c.getInputStream()){
                        byte[] buffer=new byte[4096];int n;while((n=in.read(buffer))!=-1){check(deadline);if(out.size()+n>65536)throw new IOException("Subscription too large");out.write(buffer,0,n);}
                    }
                    check(deadline);String body=out.toString(StandardCharsets.UTF_8.name());
                    try{Profile.subscription(body);}catch(IllegalArgumentException invalid){throw new IOException("Invalid subscription");}
                    cache.resource=url;cache.body=body;cache.etag=safeHeader(c.getHeaderField("ETag"));cache.modified=safeHeader(c.getHeaderField("Last-Modified"));cache.failures=0;cache.nextAttempt=0;
                    RustCore.addMetric(2,1);return body;
                }finally{current=null;c.disconnect();}
            }
            throw new IOException("Too many redirects");
        }catch(IOException error){if(!cancelled&&!Thread.currentThread().isInterrupted())failed(cache,generation);throw error;}
    }
    private static String safeHeader(String value){return value!=null&&value.length()<=1024&&value.indexOf('\r')<0&&value.indexOf('\n')<0?value:"";}
    private void check(long deadline)throws InterruptedIOException{
        if(cancelled||Thread.currentThread().isInterrupted()||System.nanoTime()>deadline)throw new InterruptedIOException("Subscription check cancelled or timed out");
    }
}
