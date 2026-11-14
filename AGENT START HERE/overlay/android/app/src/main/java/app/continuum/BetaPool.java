package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;

/** Small bounded worker pool. No API tokens, custom origins or raw UI errors. */
public final class BetaPool {
    public interface Probe {long measure(BetaCatalog.Entry entry)throws Exception;}
    private final ExecutorService workers=new ThreadPoolExecutor(3,3,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(12),new ThreadPoolExecutor.AbortPolicy());
    private final Map<Integer,BetaCatalog.Result> cached=new HashMap<>();
    public synchronized List<BetaCatalog.Result> refresh(Probe probe,boolean measure)throws Exception{
        List<Future<BetaCatalog.Result>> futures=new ArrayList<>();
        CompletionService<BetaCatalog.Result> completion=new ExecutorCompletionService<>(workers);
        Map<Integer,BetaCatalog.Result> previous=new HashMap<>(cached);
        try{
            for(int slot=1;slot<=BetaCatalog.COUNT;slot++){
                final int index=slot;
                futures.add(completion.submit(()->{
                    BetaCatalog.Result old=previous.get(index);BetaCatalog.Entry entry;
                    try{entry=BetaCatalog.parse(fetch(BetaCatalog.source(index)),index,System.currentTimeMillis()/1000);}
                    catch(Exception e){if(old==null||!old.entry.valid(System.currentTimeMillis()/1000))return null;entry=old.entry;}
                    if(old!=null&&old.entry.issued>entry.issued&&old.entry.valid(System.currentTimeMillis()/1000))entry=old.entry;
                    long latency=old!=null&&old.entry.uri.equals(entry.uri)?old.latency:-1;
                    if(measure){try{latency=probe.measure(entry);}catch(Exception e){latency=-1;}}
                    return new BetaCatalog.Result(entry,latency);
                }));
            }
            long end=System.nanoTime()+45_000_000_000L;List<BetaCatalog.Result> results=new ArrayList<>();
            for(int i=0;i<futures.size();i++){
                long left=end-System.nanoTime();if(left<=0)break;
                Future<BetaCatalog.Result> future=completion.poll(left,TimeUnit.NANOSECONDS);if(future==null)break;
                try{BetaCatalog.Result result=future.get();if(result!=null&&result.entry.valid(System.currentTimeMillis()/1000))results.add(result);}
                catch(ExecutionException e){/* One failed slot cannot reject the pool. */}
            }
            cached.clear();for(BetaCatalog.Result result:results)cached.put(result.entry.slot,result);
            results.sort(Comparator.comparingInt(r->r.entry.slot));return results;
        }finally{for(Future<?> future:futures)future.cancel(true);}
    }
    public void close(){workers.shutdownNow();}
    private static String fetch(String source)throws Exception{
        URL url=new URL(source);long end=System.nanoTime()+8_000_000_000L;
        for(int redirects=0;redirects<5;redirects++){
            if(Thread.currentThread().isInterrupted()||System.nanoTime()>=end)throw new InterruptedIOException();
            if(!"https".equals(url.getProtocol())||url.getUserInfo()!=null)throw new IOException();
            HttpsURLConnection c=(HttpsURLConnection)url.openConnection();c.setInstanceFollowRedirects(false);c.setUseCaches(false);
            c.setRequestProperty("Cache-Control","no-cache");c.setConnectTimeout(3000);c.setReadTimeout(3000);
            try{
                int code=c.getResponseCode();
                if(code==301||code==302||code==303||code==307||code==308){String location=c.getHeaderField("Location");if(location==null)throw new IOException();url=new URL(url,location);continue;}
                if(code!=200)throw new IOException();
                try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                    byte[] b=new byte[2048];int n;while((n=in.read(b))!=-1){if(out.size()+n>16384||System.nanoTime()>end||Thread.currentThread().isInterrupted())throw new IOException();out.write(b,0,n);}return out.toString(StandardCharsets.UTF_8.name());
                }
            }finally{c.disconnect();}
        }throw new IOException();
    }
}
