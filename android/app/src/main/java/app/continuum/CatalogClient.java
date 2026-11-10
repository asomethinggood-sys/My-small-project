package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import javax.net.ssl.HttpsURLConnection;

/** Separate public metadata channel. Never sends subscription or session credentials. */
public final class CatalogClient {
    public static final String URL="https://github.com/asomethinggood-sys/My-small-project/releases/download/nyx-research-catalog/catalog.json";
    private volatile HttpsURLConnection current;
    private volatile boolean cancelled;
    public void cancel(){cancelled=true;HttpsURLConnection c=current;if(c!=null)c.disconnect();}
    public static boolean allowed(java.net.URL u){return "https".equals(u.getProtocol())&&(u.getPort()==-1||u.getPort()==443)&&u.getUserInfo()==null&&Set.of("github.com","release-assets.githubusercontent.com","objects.githubusercontent.com").contains(u.getHost());}
    public String fetch()throws Exception{
        java.net.URL next=new java.net.URL(URL);
        for(int redirects=0;redirects<=4;redirects++){
            if(cancelled||!allowed(next))throw new IOException("Metadata request rejected");
            HttpsURLConnection c=(HttpsURLConnection)next.openConnection();current=c;
            try{
                c.setConnectTimeout(8000);c.setReadTimeout(8000);c.setInstanceFollowRedirects(false);c.setUseCaches(false);
                c.setRequestProperty("Accept","application/json");c.setRequestProperty("Accept-Encoding","identity");
                if(cancelled)throw new IOException("Cancelled");
                int status=c.getResponseCode();
                if(status==301||status==302||status==303||status==307||status==308){String location=c.getHeaderField("Location");if(location==null)throw new IOException("Missing redirect");next=new java.net.URL(next,location);continue;}
                if(status!=200||c.getContentLengthLong()>1048576)throw new IOException("Metadata unavailable");
                try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                    byte[] bytes=new byte[4096];int read;long start=System.nanoTime();
                    while((read=in.read(bytes))!=-1){if(cancelled||out.size()+read>1048576||System.nanoTime()-start>15_000_000_000L)throw new IOException("Metadata budget exceeded");out.write(bytes,0,read);}
                    String body=out.toString(StandardCharsets.UTF_8.name());LocationCatalog.parse(body);return body;
                }
            }finally{c.disconnect();if(current==c)current=null;}
        }
        throw new IOException("Too many redirects");
    }
}
