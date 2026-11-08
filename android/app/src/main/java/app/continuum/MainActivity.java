package app.continuum;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.net.VpnService;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int INK=0xff172f2a,MUTED=0xff6c7770,PAPER=0xfff5f4ef,LINE=0xffdedfd6,GREEN=0xff285e4a;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView state,detail,latency,endpoint,countdown,session,connect,protocolName,transportName;
    private Orbit orbit;
    private StateClient client;
    private SettingsStore store;
    private final Runnable update=new Runnable(){public void run(){render();handler.postDelayed(this,1000);}};
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);client=new StateClient(this);store=new SettingsStore(this);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(PAPER);
        LinearLayout root=column();root.setPadding(dp(26),dp(22),dp(26),dp(28));scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(26),dp(16)+insets.getSystemWindowInsetTop(),dp(26),dp(20)+insets.getSystemWindowInsetBottom());return insets.consumeSystemWindowInsets();});
        LinearLayout top=row();TextView brand=text("continuum",30,INK);brand.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        top.addView(brand,new LinearLayout.LayoutParams(0,-2,1));TextView settings=text("Settings",14,GREEN);settings.setPadding(dp(12),dp(12),0,dp(12));settings.setOnClickListener(v->settings());top.addView(settings);root.addView(top);
        add(root,text("YOUR CONNECTION. YOUR CONTROL.",10,MUTED),8,16);
        LinearLayout hero=column();hero.setGravity(Gravity.CENTER_HORIZONTAL);orbit=new Orbit();hero.addView(orbit,new LinearLayout.LayoutParams(dp(170),dp(170)));
        state=text("Offline",34,INK);state.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));hero.addView(state);
        detail=text("Tap Connect to start",13,MUTED);detail.setGravity(Gravity.CENTER);detail.setMinHeight(dp(44));hero.addView(detail);add(root,hero,0,18);
        connect=text("Connect",16,0xffffffff);connect.setTag("connect");connect.setGravity(Gravity.CENTER);connect.setBackground(box(INK,18));
        connect.setMinHeight(dp(56));connect.setOnClickListener(v->toggle());root.addView(connect,new LinearLayout.LayoutParams(-1,dp(56)));
        LinearLayout metrics=row(),left=column(),right=column();latency=text("—",25,INK);left.addView(latency);left.addView(text("HTTP CHECK · NOT PING",9,MUTED));session=text("—",25,INK);right.addView(session);right.addView(text("VPN SESSION",9,MUTED));
        metrics.addView(left,new LinearLayout.LayoutParams(0,-2,1));metrics.addView(right,new LinearLayout.LayoutParams(0,-2,1));add(root,metrics,24,22);divider(root);
        add(root,text("SELECTED CONNECTION",10,MUTED),20,10);
        LinearLayout protocol=row();protocol.setTag("profiles");protocolName=text("VLESS",17,INK);transportName=text("WebSocket · TLS  ›",12,GREEN);
        protocol.addView(protocolName,new LinearLayout.LayoutParams(0,-2,1));protocol.addView(transportName);protocol.setPadding(0,dp(12),0,dp(12));protocol.setOnClickListener(v->profiles());root.addView(protocol);
        endpoint=text("No active endpoint",12,MUTED);endpoint.setSingleLine(true);endpoint.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);add(root,endpoint,2,18);divider(root);
        LinearLayout refresh=row(),explanation=column();explanation.addView(text("Automatic recovery",15,INK));countdown=text("Updates while connected",12,MUTED);explanation.addView(countdown);refresh.addView(explanation,new LinearLayout.LayoutParams(0,-2,1));
        TextView check=text("Check now",13,GREEN);check.setPadding(dp(12),dp(12),0,dp(12));check.setOnClickListener(v->{if(client.status.running)client.refresh();else toast("Connect first to check the endpoint");});refresh.addView(check);add(root,refresh,16,16);
        TextView events=text("Connection activity  ↗",13,GREEN);events.setPadding(0,dp(12),0,dp(12));events.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("Connection activity").setMessage(client.history.isEmpty()?"No activity in this service session.":client.history).setPositiveButton("Done",null).show());root.addView(events);
        add(root,text("Server handovers can still interrupt sessions. Disconnect pauses recovery until you explicitly reconnect.",11,MUTED),12,0);
    }
    private void render(){
        VpnStatus s=client.status;state.setText(s.state);detail.setText(s.detail);endpoint.setText(s.host);latency.setText(s.latency<0?"—":s.latency+" ms");
        boolean stopping="Disconnecting".equals(s.state);connect.setText(stopping?"Disconnecting…":s.running?"Disconnect":"Connect");connect.setEnabled(!stopping);connect.setAlpha(stopping?.6f:1f);
        Profile selected=selectedProfile();protocolName.setText(s.running?s.protocol:selected==null?"VLESS":selected.protocolLabel());transportName.setText((s.running?s.transport:selected==null?"WebSocket · TLS":selected.transportLabel())+"  ›");
        long duration=s.connectedAt==0?0:(SystemClock.elapsedRealtime()-s.connectedAt)/1000;
        session.setText(s.connectedAt==0?"—":String.format(Locale.US,"%02d:%02d:%02d",duration/3600,(duration/60)%60,duration%60));
        countdown.setText(s.running?"Next check in "+Math.max(0,(s.nextCheck-SystemClock.elapsedRealtime())/1000)+"s":"Updates while connected");
        orbit.connected="Connected".equals(s.state);orbit.busy=s.running&&!orbit.connected;orbit.invalidate();
    }
    private Profile selectedProfile(){try{String manual=SettingsStore.manual(store.load());return manual==null?null:Profile.parse(manual);}catch(Exception e){return null;}}
    private void toggle(){
        if(client.status.running){client.disconnect();toast("Disconnect requested. Disable Android lockdown if it blocks Internet while paused.");return;}
        Intent consent=VpnService.prepare(this);if(consent!=null)startActivityForResult(consent,10);else startVpn();
    }
    private void startVpn(){
        client.connect();render();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==10&&result==RESULT_OK)startVpn();}
    @Override protected void onResume(){super.onResume();client.begin();handler.post(update);}
    @Override protected void onPause(){handler.removeCallbacks(update);client.end();super.onPause();}
    private void profiles(){
        try{
            JSONObject settings=store.load();JSONArray saved=settings.getJSONArray("profiles");String[] names=new String[saved.length()+1];names[0]="Automatic · project subscription";
            for(int i=0;i<saved.length();i++){Profile p=Profile.parse(saved.getJSONObject(i).getString("uri"));names[i+1]=p.label+" · "+p.protocolLabel()+" / "+p.transportLabel();}
            new AlertDialog.Builder(this).setTitle("Connection profiles")
                .setSingleChoiceItems(names,settings.optInt("selection",-1)+1,(dialog,index)->{
                    try{settings.put("selection",index-1);store.save(settings);client.refresh();render();dialog.dismiss();}
                    catch(Exception e){toast("Could not save the selected profile");}
                }).setPositiveButton("Import profile",(d,w)->importProfile()).setNeutralButton("How protocols work",(d,w)->protocolInfo())
                .setNegativeButton("Close",null).show();
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
            input.setText("");client.refresh();render();dialog.dismiss();toast("Imported "+p.protocolLabel()+". Endpoint verification happens on connection.");
        }catch(Exception error){input.setError("Invalid or unsupported profile (maximum 20 saved profiles)");}}));dialog.show();
    }
    private void settings(){
        JSONObject saved=store.load();LinearLayout fields=column();fields.setPadding(dp(24),dp(6),dp(24),0);fields.addView(text("AUTOMATIC SUBSCRIPTION · HTTPS",10,MUTED));
        EditText source=new EditText(this);source.setText(saved.optString("source",SubscriptionClient.DEFAULT));source.setTextSize(13);source.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);fields.addView(source);
        add(fields,text("REFRESH INTERVAL",10,MUTED),20,8);Spinner interval=new Spinner(this);interval.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"30 seconds · faster discovery","60 seconds · balanced","120 seconds · fewer requests"}));int seconds=saved.optInt("interval",60);interval.setSelection(seconds==30?0:seconds==120?2:1);fields.addView(interval);
        add(fields,text("Healthy, unchanged profiles get a network health check every five minutes, not on every refresh. Manual imports do not rotate with the project subscription.",12,MUTED),16,0);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Settings · 0.2").setView(fields).setPositiveButton("Save",null).setNegativeButton("Cancel",null)
            .setNeutralButton("Android VPN settings",(d,w)->{try{startActivity(new Intent(Settings.ACTION_VPN_SETTINGS));}catch(Exception e){toast("Open Android Settings → VPN");}}).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            saved.put("source",SubscriptionClient.validate(source.getText().toString())).put("interval",new int[]{30,60,120}[interval.getSelectedItemPosition()]);store.save(saved);client.refresh();dialog.dismiss();
        }catch(Exception e){source.setError("Enter a valid HTTPS subscription URL");}}));dialog.show();
    }
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);v.setFontFeatureSettings("tnum");return v;}
    private GradientDrawable box(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private void add(LinearLayout parent,View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(top),0,dp(bottom));parent.addView(view,p);}
    private void divider(LinearLayout parent){View v=new View(this);v.setBackgroundColor(LINE);parent.addView(v,new LinearLayout.LayoutParams(-1,dp(1)));}
    private int dp(float n){return(int)(getResources().getDisplayMetrics().density*n+.5f);}
    private final class Orbit extends View{
        final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);boolean connected,busy;
        Orbit(){super(MainActivity.this);}
        @Override protected void onDraw(Canvas c){float x=getWidth()/2f,y=getHeight()/2f,r=dp(62);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(1));p.setColor(LINE);c.drawCircle(x,y,r+dp(12),p);p.setStrokeWidth(dp(5));p.setColor(connected?GREEN:0xffd7dcd0);c.drawCircle(x,y,r,p);p.setColor(connected?GREEN:INK);p.setStrokeWidth(dp(4));p.setStrokeCap(Paint.Cap.ROUND);c.drawArc(x-dp(23),y-dp(23),x+dp(23),y+dp(23),-45,270,false,p);c.drawLine(x,y,x+dp(24),y,p);p.setStyle(Paint.Style.FILL);p.setColor(connected?0xffb5ce73:busy?0xffc6a360:LINE);c.drawCircle(x+r,y,dp(7),p);setContentDescription(connected?"Connected":busy?"Connection in progress":"Offline");}
    }
}
