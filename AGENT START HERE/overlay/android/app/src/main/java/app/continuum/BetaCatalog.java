package app.continuum;

import java.net.URI;
import java.util.*;
import org.json.*;

/** Strict release-record boundary; labels are local, never supplied by servers. */
public final class BetaCatalog {
    public static final int COUNT=10;
    public static final String BASE="https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-beta-";
    public static String label(int slot){if(slot<1||slot>COUNT)throw new IllegalArgumentException();return String.format(Locale.US,"US🇺🇸_%02d",slot);}
    public static String source(int slot){if(slot<1||slot>COUNT)throw new IllegalArgumentException();return BASE+String.format(Locale.US,"%02d",slot)+"/slot.json";}
    public static final class Entry {
        public final int slot;public final String generation,uri;public final long issued,expires;
        public Entry(int slot,String generation,String uri,long issued,long expires){this.slot=slot;this.generation=generation;this.uri=uri;this.issued=issued;this.expires=expires;}
        public boolean valid(long now){return issued<=now+120&&expires>now+15;}
    }
    public static Entry parse(String body,int expected,long now)throws Exception{
        if(expected<1||expected>COUNT||body.length()>16384)throw new IllegalArgumentException();
        JSONObject j=new JSONObject(body);int slot=j.getInt("slot");
        long issued=j.getLong("issued_at"),expires=j.getLong("expires_at");
        String generation=j.getString("generation"),uri=j.getString("uri");
        if(j.getInt("schema")!=1||slot!=expected||!"US".equals(j.getString("country"))||!generation.matches("[0-9]{1,24}-[0-9]{1,6}")||issued>now+120||expires<=now+15||expires<=issued||expires-issued>21600)throw new IllegalArgumentException();
        URI u=URI.create(uri);
        if(!"vless".equals(u.getScheme())||u.getHost()==null||!u.getHost().matches("[a-z0-9-]+\\.trycloudflare\\.com")||u.getPort()!=443||u.getFragment()!=null)throw new IllegalArgumentException();
        Profile profile=Profile.parse(uri); // Reject unsupported options/TLS downgrade.
        if(!"vless".equals(profile.protocol)||!"ws".equals(profile.transport)||!profile.host.equals(profile.sni)||!profile.host.equals(profile.wsHost)||!profile.path.matches("/[a-zA-Z0-9_-]{1,128}"))throw new IllegalArgumentException();
        return new Entry(slot,generation,uri,issued,expires);
    }
    public static final class Result {
        public final Entry entry;public final long latency;
        public Result(Entry entry,long latency){this.entry=entry;this.latency=latency;}
    }
    public static Result choose(List<Result> results,int preferred,long now){
        Result best=null;
        for(Result r:results){if(!r.entry.valid(now)||r.latency<0)continue;if(r.entry.slot==preferred)return r;if(best==null||r.latency<best.latency||(r.latency==best.latency&&r.entry.slot<best.entry.slot))best=r;}
        return best;
    }
    private BetaCatalog(){}
}
