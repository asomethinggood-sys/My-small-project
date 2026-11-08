package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

public final class SubscriptionClient {
    public static final String DEFAULT="https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt";
    public static String validate(String value) {
        URI uri=URI.create(value.trim());
        if (!"https".equals(uri.getScheme()) || uri.getHost()==null || uri.getUserInfo()!=null || uri.getFragment()!=null)
            throw new IllegalArgumentException("Use an HTTPS subscription URL without credentials");
        return uri.toString();
    }
    public String fetch(String source) throws IOException {
        String current=validate(source);
        for (int redirect=0; redirect<6; redirect++) {
            HttpsURLConnection c=(HttpsURLConnection)new URL(current).openConnection();
            c.setInstanceFollowRedirects(false); c.setConnectTimeout(8000); c.setReadTimeout(8000);
            c.setUseCaches(false); c.setRequestProperty("Cache-Control","no-cache");
            c.setRequestProperty("User-Agent","Continuum/0.1");
            try {
                int code=c.getResponseCode();
                if (code==301 || code==302 || code==303 || code==307 || code==308) {
                    String location=c.getHeaderField("Location");
                    if (location==null) throw new IOException("Missing redirect address");
                    current=validate(new URL(new URL(current),location).toString());
                    continue;
                }
                if (code!=200) throw new IOException("Subscription HTTP "+code);
                ByteArrayOutputStream out=new ByteArrayOutputStream();
                try (InputStream in=c.getInputStream()) {
                    byte[] block=new byte[4096]; int count;
                    while ((count=in.read(block))!=-1) {
                        if (out.size()+count>65536) throw new IOException("Subscription too large");
                        out.write(block,0,count);
                    }
                }
                return out.toString(StandardCharsets.UTF_8.name());
            } finally { c.disconnect(); }
        }
        throw new IOException("Too many HTTPS redirects");
    }
}
