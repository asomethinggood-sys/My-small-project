package app.continuum;

import android.app.*;
import android.content.*;
import android.provider.Settings;
import android.widget.*;
import org.json.*;

/** Consumer settings deliberately contain no source/profile/endpoint controls. */
public final class ContinuumSettings {
    private ContinuumSettings(){}
    public static void show(Activity context,SettingsStore store,StateClient client){
        JSONObject saved=store.load();LinearLayout fields=new LinearLayout(context);fields.setOrientation(LinearLayout.VERTICAL);
        int p=(int)(24*context.getResources().getDisplayMetrics().density);fields.setPadding(p,0,p,p);
        label(context,fields,"Check for connection updates");
        Spinner interval=spinner(context,fields,new String[]{"Every minute","Every two minutes","Every 30 seconds"});
        int seconds=saved.optInt("interval",60);interval.setSelection(seconds==120?1:seconds==30?2:0);
        if(BuildConfig.BETA_POOL){interval.setSelection(2);interval.setEnabled(false);label(context,fields,"Beta checks the server list about every 30 seconds after the previous check finishes. Android power restrictions and slow requests can delay checks.");}
        label(context,fields,"Connection compatibility");
        Spinner mtu=spinner(context,fields,new String[]{"Balanced","For unreliable networks","Standard packet size"});
        int value=NetworkConfig.mtu(saved);mtu.setSelection(value==1280?1:value==1500?2:0);
        label(context,fields,"Balanced works for most networks. If pages stall, try the option for unreliable networks. Saving this change may briefly reconnect you.");
        Switch ipv6=new Switch(context);ipv6.setText("Allow IPv6 website addresses");ipv6.setChecked(NetworkConfig.dualStack(saved));ipv6.setMinHeight(p*2);fields.addView(ipv6);
        label(context,fields,"Leave this off if your network has trouble reaching some websites. Android may delay background checks to save battery.");
        ScrollView scroll=new ScrollView(context);scroll.addView(fields);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle("Connection settings").setView(scroll)
            .setPositiveButton("Save",null).setNegativeButton("Cancel",null)
            .setNeutralButton("Android VPN settings",(d,w)->{try{context.startActivity(new Intent(Settings.ACTION_VPN_SETTINGS));}catch(Exception ignored){}}).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            // Rebuild from an allowlist, also deleting any legacy imported profile.
            JSONObject safe=ManagedSettings.apply(saved).put("interval",new int[]{60,120,30}[interval.getSelectedItemPosition()])
                .put("mtu",new int[]{1400,1280,1500}[mtu.getSelectedItemPosition()]).put("dualStack",ipv6.isChecked());
            store.save(safe);client.refresh();dialog.dismiss();
        }catch(Exception ignored){Toast.makeText(context,"Couldn't save your changes. Please try again.",Toast.LENGTH_LONG).show();}}));dialog.show();
    }
    private static Spinner spinner(Context c,LinearLayout root,String[] values){Spinner s=new Spinner(c);s.setAdapter(new ArrayAdapter<>(c,android.R.layout.simple_spinner_dropdown_item,values));root.addView(s);return s;}
    private static void label(Context c,LinearLayout root,String value){TextView t=new TextView(c);t.setText(value);t.setTextSize(14);t.setPadding(0,24,0,12);root.addView(t);}
}
