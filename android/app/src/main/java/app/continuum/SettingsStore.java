package app.continuum;

import android.content.Context;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Atomic disk handoff, not multi-process SharedPreferences caches. Only the UI writes settings. */
public final class SettingsStore {
    private final File directory;
    public SettingsStore(Context context) {directory=context.getFilesDir();}
    public JSONObject load() {
        JSONObject value=read("settings-v2.json");
        try {
            if(!value.has("source"))value.put("source",SubscriptionClient.DEFAULT);
            if(!value.has("interval"))value.put("interval",60);
            if(!value.has("selection"))value.put("selection",-1);
            if(!value.has("profiles"))value.put("profiles",new JSONArray());
        }catch(JSONException impossible){throw new IllegalStateException(impossible);}
        return value;
    }
    public void save(JSONObject value) throws IOException {write("settings-v2.json",value);}
    public boolean paused() {return new File(directory,"user-paused").exists();}
    public void pause() {
        try {if(!new File(directory,"user-paused").exists()&&!new File(directory,"user-paused").createNewFile())throw new IOException();}
        catch(IOException e){throw new IllegalStateException("Could not persist disconnect");}
    }
    public void resumeExplicitly() {
        File marker=new File(directory,"user-paused");
        if(marker.exists()&&!marker.delete())throw new IllegalStateException("Could not clear disconnect state");
    }
    public String cache(String source) {JSONObject j=read("verified-v2.json");return source.equals(j.optString("source"))?j.optString("content",""):"";}
    public void cache(String source,String content) throws Exception {write("verified-v2.json",new JSONObject().put("source",source).put("content",content));}
    private JSONObject read(String name) {
        try {byte[] data=new AtomicFile(new File(directory,name)).readFully();if(data.length>131072)return new JSONObject();return new JSONObject(new String(data,StandardCharsets.UTF_8));}
        catch(Exception e){return new JSONObject();}
    }
    private void write(String name,JSONObject value) throws IOException {
        AtomicFile file=new AtomicFile(new File(directory,name));FileOutputStream stream=null;
        try {stream=file.startWrite();stream.write(value.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);}
        catch(IOException e){file.failWrite(stream);throw e;}
    }
    public static String manual(JSONObject settings) throws JSONException {
        int selected=settings.optInt("selection",-1);
        if(selected<0)return null;
        return settings.getJSONArray("profiles").getJSONObject(selected).getString("uri");
    }
}
