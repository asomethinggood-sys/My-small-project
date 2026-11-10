package app.continuum;

import android.os.Bundle;

public final class VpnStatus {
    public final String state,detail,host,protocol,transport;
    public final long latency,nextCheck,connectedAt;
    public final boolean running,tunOpen,engineRunning;
    /** Non-secret generation counter; never expose lease tokens or credentials. */
    public long countryGeneration;
    public VpnStatus(String state,String detail,String host,String protocol,String transport,long latency,long next,long since,boolean running,boolean tun,boolean engine) {
        this.state=state;this.detail=detail;this.host=host;this.protocol=protocol;this.transport=transport;
        this.latency=latency;this.nextCheck=next;this.connectedAt=since;this.running=running;this.tunOpen=tun;this.engineRunning=engine;
    }
    public static VpnStatus offline(){return new VpnStatus("Offline","Tap Connect to start","No active endpoint","VLESS","WebSocket · TLS",-1,0,0,false,false,false);}
    public Bundle bundle(){Bundle b=new Bundle();b.putString("state",state);b.putString("detail",detail);b.putString("host",host);b.putString("protocol",protocol);b.putString("transport",transport);b.putLong("latency",latency);b.putLong("next",nextCheck);b.putLong("since",connectedAt);b.putBoolean("running",running);b.putBoolean("tun",tunOpen);b.putBoolean("engine",engineRunning);b.putLong("countryGeneration",countryGeneration);return b;}
    public static VpnStatus from(Bundle b){VpnStatus result=new VpnStatus(b.getString("state","Offline"),b.getString("detail",""),b.getString("host",""),b.getString("protocol","VLESS"),b.getString("transport","WebSocket · TLS"),b.getLong("latency",-1),b.getLong("next"),b.getLong("since"),b.getBoolean("running"),b.getBoolean("tun"),b.getBoolean("engine"));result.countryGeneration=b.getLong("countryGeneration");return result;}
}
