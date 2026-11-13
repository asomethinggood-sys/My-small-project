package app.continuum;

import android.content.Context;
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
        return BuildConfig.MANAGED_ONLY?ManagedSettings.apply(value):value;
    }
    public void save(JSONObject value) throws IOException {write("settings-v2.json",BuildConfig.MANAGED_ONLY?ManagedSettings.apply(value):value);}
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
        // AtomicFile.openRead may delete the writer's in-flight .new file.
        // Readers in the VPN process must open only the committed base file;
        // atomic rename keeps that descriptor on a complete old or new version.
        try (FileInputStream input=new FileInputStream(new File(directory,name))) {
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] chunk=new byte[4096];int count;
            while((count=input.read(chunk))!=-1){if(bytes.size()+count>131072)return new JSONObject();bytes.write(chunk,0,count);}
            return new JSONObject(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
        }
        catch(Exception e){return new JSONObject();}
    }
    private void write(String name,JSONObject value) throws IOException {
        // Use the same rename-only protocol on all supported Android versions.
        // Older AtomicFile implementations temporarily write the base in place.
        synchronized(SettingsStore.class){
            File pending=new File(directory,name+".new"),base=new File(directory,name);
            try{
                try(FileOutputStream stream=new FileOutputStream(pending)){
                    stream.write(value.toString().getBytes(StandardCharsets.UTF_8));stream.getFD().sync();
                }
                if(!pending.renameTo(base))throw new IOException("Could not commit settings");
            }finally{pending.delete();}
        }
    }
    public static String manual(JSONObject settings) throws JSONException {
        int selected=settings.optInt("selection",-1);
        if(selected<0)return null;
        return settings.getJSONArray("profiles").getJSONObject(selected).getString("uri");
    }
}
