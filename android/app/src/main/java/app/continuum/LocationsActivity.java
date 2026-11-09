package app.continuum;

import android.app.*;
import android.os.*;
import android.graphics.Typeface;
import android.text.*;
import android.view.*;
import android.widget.*;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Discovery and authenticated availability are separate. Only a fresh service row enables selection. */
public final class LocationsActivity extends Activity {
    private static final int BG=0xff111b20,INK=0xffe9eee9,MUTED=0xff99a8aa,ACCENT=0xffc2dfcc;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private LinearLayout rows;
    private TextView summary,refresh;
    private EditText search;
    private LocationCatalog catalog;
    private CatalogClient request;
    private CountryClient countryRequest;
    private final Map<String,CountryClient.Available> available=new HashMap<>();
    private StateClient routeState;
    private String serviceStatus="Country service not provisioned";
    private boolean visible,loading;
    private long generation;
    private final Runnable tick=new Runnable(){public void run(){render();handler.postDelayed(this,30000);}};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);routeState=new StateClient(this);getWindow().getDecorView().setSystemUiVisibility(0);
        LinearLayout root=column();root.setBackgroundColor(BG);root.setPadding(dp(26),dp(18),dp(26),dp(24));setContentView(root);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(26),dp(16)+insets.getSystemWindowInsetTop(),dp(26),dp(16)+insets.getSystemWindowInsetBottom());return insets.consumeSystemWindowInsets();});
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);
        TextView back=text("‹  Back",14,ACCENT);back.setMinHeight(dp(48));back.setGravity(Gravity.CENTER_VERTICAL);back.setOnClickListener(v->finish());header.addView(back,new LinearLayout.LayoutParams(0,-2,1));
        refresh=text("Refresh",14,ACCENT);refresh.setTag("refresh-catalog");refresh.setMinHeight(dp(48));refresh.setGravity(Gravity.CENTER_VERTICAL);refresh.setOnClickListener(v->fetch());header.addView(refresh);root.addView(header);
        TextView title=text("Exit locations",32,INK);title.setTypeface(Typeface.create("sans-serif-light",Typeface.NORMAL));root.addView(title);
        summary=text("30 targets · 0 available exits",13,MUTED);summary.setPadding(0,dp(12),0,dp(12));root.addView(summary);
        TextView note=text("Country selection affects only your session. Unavailable or expired country routes never fall back to the default connection.",12,MUTED);note.setPadding(0,0,0,dp(12));root.addView(note);
        LinearLayout actions=new LinearLayout(this);TextView service=text("Service settings",13,ACCENT),normal=text("Use default",13,ACCENT);service.setMinHeight(dp(48));normal.setMinHeight(dp(48));service.setGravity(Gravity.CENTER_VERTICAL);normal.setGravity(Gravity.CENTER_VERTICAL);actions.addView(service,new LinearLayout.LayoutParams(0,-2,1));actions.addView(normal);root.addView(actions);service.setOnClickListener(v->serviceSettings());normal.setOnClickListener(v->selectCountry(""));
        search=new EditText(this);search.setTag("country-search");search.setSingleLine(true);search.setHint("Search a country or code");search.setTextSize(15);search.setTextColor(INK);search.setHintTextColor(MUTED);search.setMinHeight(dp(48));root.addView(search);
        search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){render();}public void afterTextChanged(Editable s){}});
        ScrollView scroll=new ScrollView(this);rows=column();scroll.addView(rows);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        try{byte[] body=cache().readFully();if(body.length<=1048576)catalog=LocationCatalog.parse(new String(body,StandardCharsets.UTF_8));}catch(Exception ignored){}
        render();
    }
    private AtomicFile cache(){return new AtomicFile(new File(getFilesDir(),"nyx-public-catalog.json"));}
    private void fetch(){
        if(loading)return;loading=true;refresh.setText("Refreshing…");refresh.setEnabled(false);
        long ticket=++generation;CatalogClient client=new CatalogClient();request=client;
        io.execute(()->{
            String body=null;LocationCatalog result=null;
            try{body=client.fetch();result=LocationCatalog.parse(body);}catch(Exception ignored){}
            Map<String,CountryClient.Available> live=new HashMap<>();String liveStatus="Country service not provisioned";
            org.json.JSONObject settings=new SettingsStore(this).load();
            if(!settings.optString("countryService","").isEmpty()){
                liveStatus="Country service unavailable";
                try{CountryClient c=new CountryClient(new CountryClient.Source(settings));countryRequest=c;for(CountryClient.Available row:c.availability(SystemClock.elapsedRealtime()))live.put(row.country,row);liveStatus="Authenticated live availability";}catch(Exception ignored){}finally{countryRequest=null;}
            }
            final LocationCatalog next=result;final String data=body;final String resultStatus=liveStatus;
            handler.post(()->{
                if(!visible||ticket!=generation)return;
                loading=false;refresh.setText("Refresh");refresh.setEnabled(true);request=null;
                available.clear();available.putAll(live);serviceStatus=resultStatus;
                if(next!=null){catalog=next;FileOutputStream stream=null;AtomicFile file=cache();try{stream=file.startWrite();stream.write(data.getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);}catch(IOException e){file.failWrite(stream);}}
                else Toast.makeText(this,"Live metadata unavailable. Saved observations are not live exits.",Toast.LENGTH_LONG).show();
                render();
            });
        });
    }
    private void render(){
        if(rows==null)return;rows.removeAllViews();long now=System.currentTimeMillis()/1000;
        String status=catalog==null?"Not fetched":catalog.fresh(now)?"Fresh discovery snapshot":"Expired discovery snapshot";
        int usable=0;for(CountryClient.Available row:available.values())if(row.deadline>SystemClock.elapsedRealtime())usable++;
        summary.setText("30 targets · "+usable+" available countries\n"+serviceStatus+" · "+status);
        String query=search.getText().toString().trim().toLowerCase(Locale.ROOT);int count=0;
        List<String> codes=new ArrayList<>(Arrays.asList(LocationCatalog.TARGETS.split(" ")));codes.sort(Comparator.comparing(this::name));
        for(String code:codes){String name=name(code);if(!name.toLowerCase(Locale.ROOT).contains(query)&&!code.toLowerCase(Locale.ROOT).contains(query))continue;count++;
            LocationCatalog.Country country=catalog==null?null:catalog.countries.get(code);
            LinearLayout row=column();row.setPadding(0,dp(18),0,dp(18));row.setMinimumHeight(dp(76));
            TextView title=text(name+"   "+code,16,INK);row.addView(title);
            CountryClient.Available live=available.get(code);
            String label=live!=null&&live.deadline>SystemClock.elapsedRealtime()?"Available · "+live.pools+" pools · "+live.providers+" providers":country==null?"No verified exit":catalog.status(country,now);
            row.addView(text(label+"  ·  Details ›",12,MUTED));row.setTag("country-"+code);row.setOnClickListener(v->details(code,country));rows.addView(row);
            View line=new View(this);line.setBackgroundColor(0xff334146);rows.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
        }
        if(count==0){TextView empty=text("No matching countries",15,MUTED);empty.setPadding(0,dp(24),0,0);rows.addView(empty);}
    }
    private String name(String code){return new Locale("",code).getDisplayCountry(Locale.getDefault());}
    private void details(String code,LocationCatalog.Country country){
        CountryClient.Available live=available.get(code);boolean usable=live!=null&&live.deadline>SystemClock.elapsedRealtime();
        StringBuilder detail=new StringBuilder(usable?"Verified service pools: "+live.pools+"\nUDP supported · "+live.providers+" providers\n\n":"No currently verified service pool\n\n");
        if(country!=null){boolean fresh=catalog.fresh(System.currentTimeMillis()/1000);detail.append(fresh?"Discovery snapshot\n":"Historical snapshot — expired\n").append(country.discovered).append(" discovered servers · ").append(country.providers).append(" directory providers\n").append(country.advertised).append(" advertised endpoints\n\n");
            for(LocationCatalog.Exit exit:country.exits)detail.append(label(exit.provider)).append(" / ").append(exit.type.toUpperCase(Locale.ROOT)).append("\n").append(exit.discovered).append(" discovered · ").append(exit.advertised).append(" advertised\n").append("UDP: ").append("unsupported".equals(exit.udp)?"not supported":"not verified for service").append("\n\n");
        }else detail.append("No current discovery data. Refresh to request the runner's latest public metadata.\n\n");
        detail.append("Providers under review\nVPN Gate: volunteer availability and logging.\nVPNBook OpenVPN / WireGuard: sharing permission and configuration lifetime.\nWARP: no arbitrary-country selection.\nPsiphon: local OSSH tested; public country/UDP unverified.\nProton / Riseup: provisioning and entitlement.\nTor: TCP only.\n\nUDP is a capability, not a provider. Advertised protocols are not proof of a working exit.");
        AlertDialog.Builder dialog=new AlertDialog.Builder(this).setTitle(name(code)).setMessage(detail.toString()).setNegativeButton("Close",null);
        if(usable)dialog.setPositiveButton("Select country",(d,w)->{CountryClient.Available current=available.get(code);if(current!=null&&current.deadline>SystemClock.elapsedRealtime())selectCountry(code);else Toast.makeText(this,"Availability expired. Refresh first.",Toast.LENGTH_LONG).show();});
        dialog.show();
    }
    private String label(String id){switch(id){case "vpngate":return "VPN Gate";case "vpnbook":return "VPNBook";case "cloudflare":return "Cloudflare WARP";case "psiphon":return "Psiphon";case "proton":return "Proton";case "riseup":return "Riseup";case "tor":return "Tor";default:return "Unknown";}}
    private void selectCountry(String code){
        try{SettingsStore store=new SettingsStore(this);org.json.JSONObject settings=store.load();settings.put("country",code);store.save(settings);routeState.refresh();Toast.makeText(this,code.isEmpty()?"Default connection selected":"Selected "+name(code)+". Connect from the home screen; no default fallback.",Toast.LENGTH_LONG).show();render();}catch(Exception e){Toast.makeText(this,"Could not save country selection",Toast.LENGTH_LONG).show();}
    }
    private void serviceSettings(){
        SettingsStore store=new SettingsStore(this);org.json.JSONObject settings=store.load();LinearLayout fields=column();fields.setPadding(dp(24),0,dp(24),0);
        fields.addView(text("A provisioned HTTPS country service is required. Public discovery data is not a service credential.",13,MUTED));
        EditText origin=new EditText(this),user=new EditText(this),key=new EditText(this);
        origin.setHint("https://service-host");origin.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);origin.setText(settings.optString("countryService",""));
        user.setHint("User identifier");user.setText(settings.optString("countryUser",""));
        key.setHint("Provisioned access key");key.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);key.setText(settings.optString("countryKey",""));
        for(EditText field:new EditText[]{origin,user,key}){field.setTextSize(14);field.setSingleLine(true);field.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);fields.addView(field);}
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Country service").setView(fields).setPositiveButton("Save",null).setNegativeButton("Cancel",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            settings.put("countryService",origin.getText().toString().trim()).put("countryUser",user.getText().toString().trim()).put("countryKey",key.getText().toString().trim());new CountryClient.Source(settings);store.save(settings);key.setText("");available.clear();serviceStatus="Refresh to verify service availability";routeState.refresh();render();dialog.dismiss();
        }catch(Exception error){origin.setError("HTTPS origin and valid provisioned credentials required");}}));dialog.show();
        dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    }
    @Override protected void onResume(){super.onResume();visible=true;routeState.begin();handler.post(tick);}
    @Override protected void onPause(){visible=false;generation++;handler.removeCallbacks(tick);routeState.end();if(request!=null)request.cancel();if(countryRequest!=null)countryRequest.cancel();request=null;loading=false;refresh.setText("Refresh");refresh.setEnabled(true);super.onPause();}
    @Override protected void onDestroy(){io.shutdownNow();super.onDestroy();}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);v.setLineSpacing(dp(3),1);return v;}
    private int dp(float n){return(int)(getResources().getDisplayMetrics().density*n+.5f);}
}
