package app.continuum;

import android.app.*;
import android.content.*;
import android.provider.Settings;
import android.widget.*;
import org.json.*;

public final class ConnectionSettingsDialog {
    private ConnectionSettingsDialog(){}
    public static void show(Activity context,SettingsStore store,StateClient client){
        JSONObject saved=store.load();LinearLayout fields=new LinearLayout(context);fields.setOrientation(LinearLayout.VERTICAL);
        int padding=(int)(24*context.getResources().getDisplayMetrics().density);fields.setPadding(padding,8,padding,8);
        label(context,fields,"Automatic subscription · HTTPS");EditText source=new EditText(context);source.setText(saved.optString("source",SubscriptionClient.DEFAULT));source.setTextSize(13);source.setInputType(17);fields.addView(source);
        label(context,fields,"Subscription refresh (screen on)");Spinner interval=spinner(context,fields,new String[]{"30 seconds","60 seconds · balanced","120 seconds · fewer requests"});int seconds=saved.optInt("interval",60);interval.setSelection(seconds==30?0:seconds==120?2:1);
        label(context,fields,"Website DNS compatibility");Spinner dns=spinner(context,fields,new String[]{"IPv4 answers · recommended for IPv4-only servers","IPv4 + IPv6 answers · needs server IPv6"});dns.setSelection(NetworkConfig.dualStack(saved)?1:0);
        label(context,fields,"Packet size (MTU)");Spinner mtu=spinner(context,fields,new String[]{"1280 · conservative","1400 · balanced","1500 · standard"});int current=NetworkConfig.mtu(saved);mtu.setSelection(current==1280?0:current==1500?2:1);
        label(context,fields,"DNS uses cached, certificate-verified HTTPS through the proxy. HTTP Host/TLS SNI recovery helps with stale destination IPs; TLS content is not decrypted. IPv6 routes remain inside the VPN in IPv4-answer mode. Custom app/browser secure DNS can bypass the DNS policy.");
        label(context,fields,"Screen off: subscription checks no faster than 120s; health checks every 15 minutes. Failed subscription fetches back off up to 15 minutes without replacing a working tunnel. Check now and default-network changes bypass that backoff. No wake lock or alarm is used.");
        label(context,fields,"Changing DNS/MTU rebuilds the engine and can interrupt sessions. Rust migration is staged: scheduling/session policy is Rust; Android adapters, profile parsing and the Go Xray engine remain.");
        Button diagnostics=new Button(context);diagnostics.setText("View / share redacted diagnostics");fields.addView(diagnostics);
        diagnostics.setOnClickListener(v->{
            String report=client.diagnostics;
            new AlertDialog.Builder(context).setTitle("Local diagnostic snapshot").setMessage(report)
                .setPositiveButton("Check now",(d,w)->client.refresh()).setNegativeButton("Close",null)
                .setNeutralButton("Share",(d,w)->{Intent share=new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,report);context.startActivity(Intent.createChooser(share,"Share redacted diagnostics"));}).show();
        });
        ScrollView scroll=new ScrollView(context);scroll.addView(fields);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle("Settings · "+BuildConfig.VERSION_NAME).setView(scroll).setPositiveButton("Save",null).setNegativeButton("Cancel",null)
            .setNeutralButton("Android VPN",(d,w)->{try{context.startActivity(new Intent(Settings.ACTION_VPN_SETTINGS));}catch(Exception ignored){}}).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            saved.put("source",SubscriptionClient.validate(source.getText().toString())).put("interval",new int[]{30,60,120}[interval.getSelectedItemPosition()]);
            saved.put("dualStack",dns.getSelectedItemPosition()==1).put("mtu",new int[]{1280,1400,1500}[mtu.getSelectedItemPosition()]);store.save(saved);client.refresh();dialog.dismiss();
        }catch(Exception error){source.setError("Could not save settings; check the HTTPS URL");}}));dialog.show();
    }
    private static Spinner spinner(Context c,LinearLayout parent,String[] items){Spinner v=new Spinner(c);v.setAdapter(new ArrayAdapter<>(c,android.R.layout.simple_spinner_dropdown_item,items));parent.addView(v);return v;}
    private static void label(Context c,LinearLayout parent,String text){TextView v=new TextView(c);v.setText(text);v.setTextSize(12);v.setPadding(0,22,0,8);parent.addView(v);}
}
