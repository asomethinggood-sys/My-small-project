package app.continuum;

import org.junit.BeforeClass;
import org.junit.Test;
import java.io.*;
import java.net.*;
import java.security.cert.Certificate;
import java.util.*;
import javax.net.ssl.HttpsURLConnection;
import static org.junit.Assert.*;

/** HTTPS simulation: never sends test credentials or requests to an external server. */
public class SubscriptionHttpTest {
    private static final Map<String,ArrayDeque<Response>> replies=new HashMap<>();
    private static final List<FakeConnection> requests=new ArrayList<>();
    private record Response(int code,String body,Map<String,String> headers){}
    @BeforeClass public static void handler(){URL.setURLStreamHandlerFactory(protocol->"https".equals(protocol)?new URLStreamHandler(){
        protected URLConnection openConnection(URL url)throws IOException{
            ArrayDeque<Response> q=replies.get(url.toString());if(q==null||q.isEmpty())throw new IOException("Unexpected test request");
            FakeConnection c=new FakeConnection(url,q.remove());requests.add(c);return c;
        }
    }:null);}
    private static void reply(String url,int code,String body,String... headers){Map<String,String> values=new HashMap<>();for(int i=0;i<headers.length;i+=2)values.put(headers[i],headers[i+1]);replies.computeIfAbsent(url,k->new ArrayDeque<>()).add(new Response(code,body,values));}
    private static final class FakeConnection extends HttpsURLConnection {
        private final Response response;
        FakeConnection(URL url,Response response){super(url);this.response=response;}
        public int getResponseCode(){if("yes".equals(response.headers().get("Test-Force-Refresh")))SubscriptionClient.forceNext();return response.code();}
        public String getHeaderField(String name){return response.headers().get(name);}
        public InputStream getInputStream(){return new ByteArrayInputStream(response.body().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
        public void connect(){}public void disconnect(){}public boolean usingProxy(){return false;}
        public String getCipherSuite(){return "test";}public Certificate[] getLocalCertificates(){return null;}public Certificate[] getServerCertificates(){return new Certificate[0];}
    }
    @Test public void etagAnd304ReuseValidatedBody()throws Exception{
        String url="https://fixture.invalid/etag";reply(url,200,ProfileTest.URI,"ETag","\"one\"");assertEquals(ProfileTest.URI,new SubscriptionClient().fetch(url));
        reply(url,304,"");assertEquals(ProfileTest.URI,new SubscriptionClient().fetch(url));assertEquals("\"one\"",requests.get(requests.size()-1).getRequestProperty("If-None-Match"));
    }
    @Test public void validatorsStayOnExactRedirectResource()throws Exception{
        String origin="https://fixture.invalid/redirect",target="https://other.invalid/object";
        reply(origin,302,"","Location",target);reply(target,200,ProfileTest.URI,"ETag","resource");new SubscriptionClient().fetch(origin);
        reply(origin,302,"","Location",target);reply(target,304,"");new SubscriptionClient().fetch(origin);
        assertNull(requests.get(requests.size()-2).getRequestProperty("If-None-Match"));assertEquals("resource",requests.get(requests.size()-1).getRequestProperty("If-None-Match"));
    }
    @Test public void unsolicited304IsRejected()throws Exception{
        String url="https://fixture.invalid/no-body";reply(url,304,"");try{new SubscriptionClient().fetch(url);fail();}catch(IOException expected){}
    }
    @Test public void invalidBodyCannotReplaceValidatedCache()throws Exception{
        String url="https://fixture.invalid/invalid";reply(url,200,ProfileTest.URI,"ETag","good");new SubscriptionClient().fetch(url);
        reply(url,200,"not a profile","ETag","bad");try{new SubscriptionClient().fetch(url);fail();}catch(IOException expected){}
        SubscriptionClient.forceNext();reply(url,304,"");assertEquals(ProfileTest.URI,new SubscriptionClient().fetch(url));assertEquals("good",requests.get(requests.size()-1).getRequestProperty("If-None-Match"));
    }
    @Test public void manualRetryBypassesBackoff()throws Exception{
        String url="https://fixture.invalid/retry";reply(url,503,"");try{new SubscriptionClient().fetch(url);fail();}catch(IOException expected){}
        int count=requests.size();try{new SubscriptionClient().fetch(url);fail();}catch(IOException expected){}assertEquals(count,requests.size());
        SubscriptionClient.forceNext();reply(url,200,ProfileTest.URI);assertEquals(ProfileTest.URI,new SubscriptionClient().fetch(url));
    }
    @Test public void cancellationDoesNotMakeRequest()throws Exception{
        int count=requests.size();SubscriptionClient c=new SubscriptionClient();c.cancel();try{c.fetch("https://fixture.invalid/cancelled");fail();}catch(InterruptedIOException expected){}assertEquals(count,requests.size());
    }
    @Test public void inFlightFailureCannotUndoNewerManualRetry()throws Exception{
        String url="https://fixture.invalid/race";reply(url,503,"","Test-Force-Refresh","yes");
        try{new SubscriptionClient().fetch(url);fail();}catch(IOException expected){}
        reply(url,200,ProfileTest.URI);assertEquals(ProfileTest.URI,new SubscriptionClient().fetch(url));
    }
    @Test public void lastModifiedUsedWhenEtagAbsent()throws Exception{
        String url="https://fixture.invalid/modified",date="Wed, 21 Oct 2015 07:28:00 GMT";
        reply(url,200,ProfileTest.URI,"Last-Modified",date);new SubscriptionClient().fetch(url);reply(url,304,"");new SubscriptionClient().fetch(url);
        assertEquals(date,requests.get(requests.size()-1).getRequestProperty("If-Modified-Since"));
    }
    @Test public void redirectDowngradeRejectedBeforeSecondRequest()throws Exception{
        String url="https://fixture.invalid/downgrade";reply(url,302,"","Location","http://fixture.invalid/plain");int count=requests.size();
        try{new SubscriptionClient().fetch(url);fail();}catch(IllegalArgumentException expected){}assertEquals(count+1,requests.size());
    }
}
