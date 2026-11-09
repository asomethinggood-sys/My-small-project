package app.continuum;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.net.VpnService;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int INK=0xffe9eee9,MUTED=0xff99a8aa,PAPER=0xff111b20,LINE=0xff334146,GREEN=0xffc2dfcc;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView state,detail,latency,endpoint,countdown,session,connect,protocolName,transportName;
    private NyxOrbit orbit;
    private StateClient client;
    private SettingsStore store;
    private Profile selected;
    private final Runnable update=new Runnable(){public void run(){render();handler.postDelayed(this,1000);}};
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);client=new StateClient(this);store=new SettingsStore(this);
        getWindow().getDecorView().setSystemUiVisibility(0);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(PAPER);
        LinearLayout root=column();root.setPadding(dp(26),dp(22),dp(26),dp(28));scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(26),dp(16)+insets.getSystemWindowInsetTop(),dp(26),dp(20)+insets.getSystemWindowInsetBottom());return insets.consumeSystemWindowInsets();});
        LinearLayout top=row();TextView brand=text("NYX",27,INK);brand.setLetterSpacing(.14f);brand.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        top.addView(brand,new LinearLayout.LayoutParams(0,-2,1));TextView settings=text("Settings",14,GREEN);settings.setMinHeight(dp(48));settings.setGravity(Gravity.CENTER);settings.setPadding(dp(16),dp(12),0,dp(12));settings.setOnClickListener(v->ConnectionSettingsDialog.show(this,store,client));top.addView(settings);root.addView(top);
        add(root,text("VPN  /  YOUR CONNECTION, UNDER CONTROL",10,MUTED),4,14);
        LinearLayout hero=column();hero.setGravity(Gravity.CENTER_HORIZONTAL);orbit=new NyxOrbit(this);hero.addView(orbit,new LinearLayout.LayoutParams(dp(190),dp(190)));
        state=text("Offline",36,INK);state.setTypeface(Typeface.create("sans-serif-light",Typeface.NORMAL));state.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);hero.addView(state);
        detail=text("Your next connection starts here.",13,MUTED);detail.setGravity(Gravity.CENTER);detail.setMinHeight(dp(48));hero.addView(detail);add(root,hero,0,20);
        connect=text("Connect",16,PAPER);connect.setTag("connect");connect.setGravity(Gravity.CENTER);connect.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22404f47),box(GREEN,28),null));
        connect.setMinHeight(dp(56));connect.setOnClickListener(v->toggle());root.addView(connect,new LinearLayout.LayoutParams(-1,dp(56)));
        LinearLayout metrics=row(),left=column(),right=column();latency=text("—",25,INK);left.addView(latency);left.addView(text("HTTP CHECK · NOT PING",9,MUTED));session=text("—",25,INK);right.addView(session);right.addView(text("VPN SESSION",9,MUTED));
        metrics.addView(left,new LinearLayout.LayoutParams(0,-2,1));metrics.addView(right,new LinearLayout.LayoutParams(0,-2,1));add(root,metrics,24,22);divider(root);
        LinearLayout location=row(),locationText=column();locationText.addView(text("Exit locations",16,INK));locationText.addView(text("Availability, providers & capabilities",12,MUTED));location.addView(locationText,new LinearLayout.LayoutParams(0,-2,1));location.addView(text("Explore  ›",13,GREEN));location.setTag("locations");location.setMinHeight(dp(72));location.setOnClickListener(v->startActivity(new Intent(this,LocationsActivity.class)));root.addView(location);divider(root);
        add(root,text("CONNECTION PROFILE",10,MUTED),20,10);
        LinearLayout protocol=row();protocol.setTag("profiles");protocolName=text("VLESS",17,INK);transportName=text("WebSocket · TLS  ›",12,GREEN);
        protocol.addView(protocolName,new LinearLayout.LayoutParams(0,-2,1));protocol.addView(transportName);protocol.setPadding(0,dp(12),0,dp(12));protocol.setOnClickListener(v->profiles());root.addView(protocol);
        endpoint=text("No active endpoint",12,MUTED);endpoint.setSingleLine(true);endpoint.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);add(root,endpoint,2,18);divider(root);
        LinearLayout refresh=row(),explanation=column();explanation.addView(text("Automatic recovery",15,INK));countdown=text("Updates while connected",12,MUTED);explanation.addView(countdown);refresh.addView(explanation,new LinearLayout.LayoutParams(0,-2,1));
        TextView check=text("Check now",13,GREEN);check.setPadding(dp(12),dp(12),0,dp(12));check.setOnClickListener(v->{if(client.status.running)client.refresh();else toast("Connect first to check the endpoint");});refresh.addView(check);add(root,refresh,16,16);
        TextView events=text("Connection activity  ↗",13,GREEN);events.setPadding(0,dp(12),0,dp(12));events.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("Connection activity").setMessage(client.history.isEmpty()?"No activity in this service session.":client.history).setPositiveButton("Done",null).show());root.addView(events);
        add(root,text("Disconnect always pauses recovery. Server handovers may interrupt active sessions.",11,MUTED),12,0);
        TextView build=text("NYX  /  "+BuildConfig.VERSION_NAME+"  ·  RUST CORE + XRAY",9,MUTED);build.setLetterSpacing(.08f);add(root,build,24,0);
    }
    private void render(){
        VpnStatus s=client.status;state.setText(s.state);detail.setText(s.detail);endpoint.setText(s.host);latency.setText(s.latency<0?"—":s.latency+" ms");
        boolean stopping="Disconnecting".equals(s.state);connect.setText(stopping?"Disconnecting…":s.running?"Disconnect":"Connect");connect.setEnabled(!stopping);connect.setAlpha(stopping?.6f:1f);
        protocolName.setText(s.running?s.protocol:selected==null?"VLESS":selected.protocolLabel());transportName.setText((s.running?s.transport:selected==null?"WebSocket · TLS":selected.transportLabel())+"  ›");
        long duration=s.connectedAt==0?0:(SystemClock.elapsedRealtime()-s.connectedAt)/1000;
        session.setText(s.connectedAt==0?"—":String.format(Locale.US,"%02d:%02d:%02d",duration/3600,(duration/60)%60,duration%60));
        countdown.setText(s.running?"Next check in "+Math.max(0,(s.nextCheck-SystemClock.elapsedRealtime())/1000)+"s":"Updates while connected");
        orbit.phase(RustCore.connectionPhase(s.running,s.tunOpen,s.engineRunning,"Connected".equals(s.state),stopping));
    }
    private void selectionChanged(){try{String manual=SettingsStore.manual(store.load());selected=manual==null?null:Profile.parse(manual);}catch(Exception ignored){selected=null;}}
    private void toggle(){
        if(client.status.running){client.disconnect();render();toast("Disconnect requested. Disable Android lockdown if it blocks Internet while paused.");return;}
        Intent consent=VpnService.prepare(this);if(consent!=null)startActivityForResult(consent,10);else startVpn();
    }
    private void startVpn(){
        client.connect();render();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==10&&result==RESULT_OK)startVpn();}
    @Override protected void onResume(){super.onResume();selectionChanged();client.begin();handler.post(update);}
    @Override protected void onPause(){handler.removeCallbacks(update);client.end();super.onPause();}
    private void profiles(){
        try{
            JSONObject settings=store.load();JSONArray saved=settings.getJSONArray("profiles");String[] names=new String[saved.length()+1];names[0]="Automatic · project subscription";
            for(int i=0;i<saved.length();i++){Profile p=Profile.parse(saved.getJSONObject(i).getString("uri"));names[i+1]=p.label+" · "+p.protocolLabel()+" / "+p.transportLabel();}
            new AlertDialog.Builder(this).setTitle("Connection profiles")
                .setSingleChoiceItems(names,settings.optInt("selection",-1)+1,(dialog,index)->{
                    try{settings.put("selection",index-1);store.save(settings);selectionChanged();client.refresh();render();dialog.dismiss();}catch(Exception e){toast("Could not save the selected profile");}
                }).setPositiveButton("Import profile",(d,w)->importProfile()).setNeutralButton("How protocols work",(d,w)->protocolInfo()).setNegativeButton("Close",null).show();
        }catch(Exception e){toast("Could not load profiles");}
    }
    private void protocolInfo(){new AlertDialog.Builder(this).setTitle("Protocol ≠ transport ≠ encryption")
        .setMessage("VLESS and VMess: TCP + TLS or WebSocket + TLS.\nTrojan: TCP + TLS or WebSocket + TLS.\nShadowsocks: supported AEAD methods over TCP/UDP.\n\nWebSocket and TLS are not standalone VPN protocols. Your project subscription remains VLESS + WebSocket + TLS. Import a matching server profile to use another combination. Plain VLESS, REALITY, plugins and unsupported options are rejected, not silently ignored.")
        .setPositiveButton("Done",null).show();}
    private void importProfile(){
        EditText input=new EditText(this);input.setHint("vless://, vmess://, trojan:// or ss://");input.setMinLines(3);input.setMaxLines(6);input.setTextSize(13);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        LinearLayout box=column();box.setPadding(dp(24),0,dp(24),0);box.addView(input);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Import a server profile").setView(box).setPositiveButton("Import",null).setNegativeButton("Cancel",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            String uri=Profile.single(input.getText().toString());Profile p=Profile.parse(uri);JSONObject settings=store.load();JSONArray entries=settings.getJSONArray("profiles");
            if(entries.length()>=20)throw new IllegalArgumentException();entries.put(new JSONObject().put("uri",uri));settings.put("selection",entries.length()-1);store.save(settings);
            input.setText("");selectionChanged();client.refresh();render();dialog.dismiss();toast("Imported "+p.protocolLabel()+". Reachability is checked on connection.");
        }catch(Exception error){input.setError("Invalid or unsupported profile (maximum 20 saved profiles)");}}));dialog.show();
    }
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);v.setFontFeatureSettings("tnum");return v;}
    private GradientDrawable box(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private void add(LinearLayout parent,View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(top),0,dp(bottom));parent.addView(view,p);}
    private void divider(LinearLayout parent){View v=new View(this);v.setBackgroundColor(LINE);parent.addView(v,new LinearLayout.LayoutParams(-1,dp(1)));}
    private int dp(float n){return(int)(getResources().getDisplayMetrics().density*n+.5f);}
}
