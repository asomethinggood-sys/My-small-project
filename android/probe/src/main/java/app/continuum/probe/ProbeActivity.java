package app.continuum.probe;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Separate UID. No production debug hooks; all traffic must traverse Android TUN. */
public final class ProbeActivity extends Activity {
    private final StringBuilder report=new StringBuilder();
    private interface Check {void run()throws Exception;}
    private void check(String name,Check task)throws Exception{long start=SystemClock.elapsedRealtime();task.run();report.append(name).append(": PASS in ").append(SystemClock.elapsedRealtime()-start).append(" ms\n");}
    private static void require(boolean okay,String message)throws IOException{if(!okay)throw new IOException(message);}
    @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(()->{
        String result="FAIL";
        try{
            check("TCP proxy-only marker",()->{require("continuum-vpn-path-ok".equals(http("http://198.18.0.42/marker")),"marker mismatch");});
            check("DNS UDP A through DoH, with server UDP/53 blocked",()->dns(false,1,true));
            check("DNS TCP A through DoH",()->dns(true,1,true));
            check("Cached repeat A query",()->dns(false,1,true));
            check("IPv4 compatibility returns no AAAA",()->dns(false,28,false));
            check("HTTP Host recovery from unusable destination IP",this::sniff);
            check("Large download with exact byte validation",this::largeDownload);
            check("Large upload with exact echo validation",this::upload);
            check("UDP through proxy",this::udp);
            check("Real domain HTTPS and certificate verification",()->{
                HttpsURLConnection c=(HttpsURLConnection)new URL("https://example.com/").openConnection();
                c.setConnectTimeout(15000);c.setReadTimeout(15000);
                try{require(c.getResponseCode()==200,"HTTPS response");try(InputStream in=c.getInputStream()){require(in.read()!=-1,"empty HTTPS body");}}finally{c.disconnect();}
            });
            result="PASS";
        }catch(Exception e){report.append("FAIL: ").append(e.getClass().getSimpleName()).append(": ").append(e.getMessage());android.util.Log.e("ContinuumProbe",report.toString(),e);}
        try{save("report",report.toString());save("result",result);}catch(Exception ignored){}
        runOnUiThread(this::finish);
    },"vpn-path-test").start();}
    private void save(String name,String text)throws Exception{try(FileOutputStream out=openFileOutput(name,MODE_PRIVATE)){out.write(text.getBytes(StandardCharsets.UTF_8));}}
    private HttpURLConnection connection(String url)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(15000);return c;}
    private String http(String url)throws Exception{HttpURLConnection c=connection(url);try{require(c.getResponseCode()==200,"HTTP status");ByteArrayOutputStream out=new ByteArrayOutputStream();try(InputStream in=c.getInputStream()){byte[] b=new byte[1024];int n;while((n=in.read(b))!=-1){require(out.size()<4096,"oversized marker");out.write(b,0,n);}}return out.toString("UTF-8");}finally{c.disconnect();}}
    private byte[] query(int type)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeShort(0x1234);out.writeShort(0x0100);out.writeShort(1);out.writeShort(0);out.writeShort(0);out.writeShort(0);
        for(String label:"example.com".split("\\.")){out.writeByte(label.length());out.writeBytes(label);}out.writeByte(0);out.writeShort(type);out.writeShort(1);return bytes.toByteArray();
    }
    private void dns(boolean tcp,int type,boolean answers)throws Exception{
        byte[] query=query(type),response;
        if(tcp){try(Socket socket=new Socket()){socket.connect(new InetSocketAddress("172.30.0.1",53),10000);socket.setSoTimeout(12000);DataOutputStream out=new DataOutputStream(socket.getOutputStream());out.writeShort(query.length);out.write(query);out.flush();DataInputStream in=new DataInputStream(socket.getInputStream());response=new byte[in.readUnsignedShort()];in.readFully(response);}}
        else{try(DatagramSocket socket=new DatagramSocket()){socket.setSoTimeout(12000);socket.send(new DatagramPacket(query,query.length,InetAddress.getByName("172.30.0.1"),53));DatagramPacket reply=new DatagramPacket(new byte[4096],4096);socket.receive(reply);response=java.util.Arrays.copyOf(reply.getData(),reply.getLength());}}
        require(response.length>=12&&response[0]==0x12&&response[1]==0x34,"DNS transaction");require((response[3]&15)==0,"DNS rcode "+(response[3]&15));
        int count=((response[6]&255)<<8)|(response[7]&255);require(answers?count>0:count==0,"unexpected DNS answer count "+count);
    }
    private void sniff()throws Exception{
        try(Socket socket=new Socket()){socket.connect(new InetSocketAddress("198.18.0.99",80),10000);socket.setSoTimeout(10000);
            socket.getOutputStream().write("GET /marker HTTP/1.1\r\nHost: marker.continuum.invalid\r\nConnection: close\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[1024];int n;while((n=socket.getInputStream().read(b))!=-1){require(out.size()<8192,"oversized response");out.write(b,0,n);}
            require(out.toString("UTF-8").contains("continuum-vpn-path-ok"),"Host sniff did not recover destination");
        }
    }
    private void largeDownload()throws Exception{
        HttpURLConnection c=connection("http://198.18.0.42/large");
        try{require(c.getResponseCode()==200,"large response");int offset=0;try(InputStream in=c.getInputStream()){byte[] b=new byte[16384];int n;while((n=in.read(b))!=-1){for(int i=0;i<n;i++)require((b[i]&255)==(offset+i)%251,"download byte mismatch");offset+=n;require(offset<=524288,"excess download");}}require(offset==524288,"truncated download");}finally{c.disconnect();}
    }
    private void upload()throws Exception{
        byte[] body=new byte[65536];for(int i=0;i<body.length;i++)body[i]=(byte)(i%251);
        HttpURLConnection c=connection("http://198.18.0.42/echo");c.setRequestMethod("POST");c.setDoOutput(true);c.setFixedLengthStreamingMode(body.length);
        try{try(OutputStream out=c.getOutputStream()){out.write(body);}require(c.getResponseCode()==200,"upload response");try(InputStream in=c.getInputStream()){for(byte expected:body)require(in.read()==(expected&255),"upload echo mismatch");require(in.read()==-1,"excess echo");}}finally{c.disconnect();}
    }
    private void udp()throws Exception{
        byte[] data=new byte[1200];for(int i=0;i<data.length;i++)data[i]=(byte)(i%251);
        try(DatagramSocket socket=new DatagramSocket()){socket.setSoTimeout(10000);socket.send(new DatagramPacket(data,data.length,InetAddress.getByName("198.18.0.43"),18781));DatagramPacket reply=new DatagramPacket(new byte[2048],2048);socket.receive(reply);require(reply.getLength()==data.length,"UDP length");for(int i=0;i<data.length;i++)require(reply.getData()[i]==data[i],"UDP payload");}
    }
}
