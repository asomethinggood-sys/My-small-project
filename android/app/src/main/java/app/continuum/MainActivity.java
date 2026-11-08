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
import java.util.Locale;

/** Original native interface: no WebView, analytics, remote fonts or UI framework. */
public final class MainActivity extends Activity {
    private static final int INK=0xff172f2a, MUTED=0xff6c7770, PAPER=0xfff5f4ef, LINE=0xffdedfd6, GREEN=0xff285e4a;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView state, detail, latency, endpoint, countdown, session, connect;
    private Orbit orbit;
    private final Runnable update=new Runnable(){public void run(){render();handler.postDelayed(this,1000);}};
    private android.content.SharedPreferences prefs;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved); prefs=getSharedPreferences("continuum",MODE_PRIVATE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        ScrollView scroll=new ScrollView(this); scroll.setFillViewport(true); scroll.setBackgroundColor(PAPER);
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(26),dp(22),dp(26),dp(28));
        scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{
            root.setPadding(dp(26),dp(16)+insets.getSystemWindowInsetTop(),dp(26),dp(20)+insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        LinearLayout top=row();
        TextView brand=text("continuum",30,INK); brand.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        top.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
        TextView settings=text("Settings",14,GREEN); settings.setPadding(dp(12),dp(12),0,dp(12));settings.setOnClickListener(v->settings());top.addView(settings);
        root.addView(top);add(root,text("A LITTLE LESS RECONNECTING.",10,MUTED),8,20);
        LinearLayout hero=new LinearLayout(this);hero.setOrientation(LinearLayout.VERTICAL);hero.setGravity(Gravity.CENTER_HORIZONTAL);
        orbit=new Orbit();hero.addView(orbit,new LinearLayout.LayoutParams(dp(184),dp(184)));
        state=text("Offline",36,INK);state.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));hero.addView(state);
        detail=text("Ready when you are",13,MUTED);detail.setGravity(Gravity.CENTER);detail.setMinHeight(dp(44));hero.addView(detail);
        add(root,hero,0,20);
        connect=text("Connect",16,0xffffffff);connect.setGravity(Gravity.CENTER);connect.setBackground(box(INK,18));
        connect.setMinHeight(dp(56));connect.setOnClickListener(v->toggle());root.addView(connect,new LinearLayout.LayoutParams(-1,dp(56)));
        LinearLayout metrics=row();
        LinearLayout l=column();latency=text("—",25,INK);l.addView(latency);l.addView(text("HTTP CHECK · NOT PING",9,MUTED));
        LinearLayout r=column();session=text("—",25,INK);r.addView(session);r.addView(text("VPN SESSION",9,MUTED));
        metrics.addView(l,new LinearLayout.LayoutParams(0,-2,1));metrics.addView(r,new LinearLayout.LayoutParams(0,-2,1));add(root,metrics,25,24);
        divider(root);
        add(root,text("CONNECTION",10,MUTED),20,12);
        LinearLayout protocol=row();protocol.addView(text("VLESS",17,INK),new LinearLayout.LayoutParams(0,-2,1));
        TextView badge=text("WS + TLS  ›",12,GREEN); protocol.addView(badge);protocol.setPadding(0,dp(10),0,dp(10));protocol.setOnClickListener(v->protocols());root.addView(protocol);
        endpoint=text("No active endpoint",12,MUTED);endpoint.setSingleLine(true);endpoint.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);add(root,endpoint,2,18);
        divider(root);
        LinearLayout refresh=row(); LinearLayout explanation=column();explanation.addView(text("Automatic recovery",15,INK));
        countdown=text("Updates while connected",12,MUTED);explanation.addView(countdown);refresh.addView(explanation,new LinearLayout.LayoutParams(0,-2,1));
        TextView check=text("Check now",13,GREEN);check.setPadding(dp(12),dp(12),0,dp(12));check.setOnClickListener(v->{if(TunnelService.snapshot.running)startForegroundService(new Intent(this,TunnelService.class).setAction(TunnelService.REFRESH));else Toast.makeText(this,"Connect first to check and recover",Toast.LENGTH_SHORT).show();});refresh.addView(check);add(root,refresh,16,16);
        TextView events=text("Connection activity  ↗",13,GREEN);events.setPadding(0,dp(12),0,dp(12));events.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("Connection activity").setMessage(TunnelService.history().isEmpty()?"No activity this session.":TunnelService.history()).setPositiveButton("Done",null).show());root.addView(events);
        add(root,text("Built for rotating endpoints. A server handover can still interrupt calls and downloads.",11,MUTED),14,0);
    }
    private void render() {
        TunnelService.Snapshot s=TunnelService.snapshot;
        state.setText(s.state);detail.setText(s.detail);endpoint.setText(s.host);
        latency.setText(s.latency<0?"—":s.latency+" ms");
        connect.setText(s.running?"Disconnect":"Connect");
        long duration=s.connectedAt==0?0:(SystemClock.elapsedRealtime()-s.connectedAt)/1000;
        session.setText(s.connectedAt==0?"—":String.format(Locale.US,"%02d:%02d:%02d",duration/3600,(duration/60)%60,duration%60));
        countdown.setText(s.running?"Next check in "+Math.max(0,(s.nextCheck-SystemClock.elapsedRealtime())/1000)+"s":"Updates while connected");
        orbit.connected="Connected".equals(s.state);orbit.busy=s.running&&!orbit.connected;orbit.invalidate();
    }
    private void toggle() {
        if(TunnelService.snapshot.running){startService(new Intent(this,TunnelService.class).setAction(TunnelService.STOP));return;}
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
        Intent permission=VpnService.prepare(this);
        if(permission!=null) startActivityForResult(permission,10); else startVpn();
    }
    private void startVpn(){startForegroundService(new Intent(this,TunnelService.class));}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==10&&result==RESULT_OK)startVpn();}
    @Override protected void onResume(){super.onResume();handler.post(update);}
    @Override protected void onPause(){handler.removeCallbacks(update);super.onPause();}
    private void protocols(){new AlertDialog.Builder(this).setTitle("Protocol")
        .setMessage("VLESS · WebSocket · TLS\n\nThis is the protocol your server provides. VMess, Trojan and other transports need compatible servers; they are not fake switches in this app.")
        .setPositiveButton("Done",null).show();}
    private void settings(){
        LinearLayout fields=column();fields.setPadding(dp(24),dp(6),dp(24),0);
        fields.addView(text("SUBSCRIPTION · HTTPS ONLY",10,MUTED));
        EditText source=new EditText(this);source.setText(prefs.getString("source",SubscriptionClient.DEFAULT));source.setTextSize(13);source.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);fields.addView(source);
        add(fields,text("CHECK INTERVAL",10,MUTED),20,8);
        Spinner interval=new Spinner(this);interval.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"30 seconds · quicker recovery","60 seconds · balanced","120 seconds · fewer requests"}));
        int saved=prefs.getInt("interval",60);interval.setSelection(saved==30?0:saved==120?2:1);fields.addView(interval);
        add(fields,text("Updates are validated before switching. Bad updates keep the last profile. Always-on can restart the app, but does not remove server outages.",12,MUTED),16,0);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Connection settings").setView(fields)
            .setPositiveButton("Save",null).setNegativeButton("Cancel",null)
            .setNeutralButton("Android VPN settings",(d,w)->{try{startActivity(new Intent(Settings.ACTION_VPN_SETTINGS));}catch(Exception e){Toast.makeText(this,"Open Android Settings → VPN",Toast.LENGTH_LONG).show();}}).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            String url=SubscriptionClient.validate(source.getText().toString());
            android.content.SharedPreferences.Editor edit=prefs.edit();
            if(!url.equals(prefs.getString("source",SubscriptionClient.DEFAULT)))edit.remove("verified");
            edit.putString("source",url).putInt("interval",new int[]{30,60,120}[interval.getSelectedItemPosition()]).apply();
            if(TunnelService.snapshot.running)startForegroundService(new Intent(this,TunnelService.class).setAction(TunnelService.REFRESH));
            dialog.dismiss();
        }catch(Exception e){source.setError("Enter a valid HTTPS subscription URL");}}));dialog.show();
    }
    private LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);v.setFontFeatureSettings("tnum");return v;}
    private GradientDrawable box(int color,int radius){GradientDrawable b=new GradientDrawable();b.setColor(color);b.setCornerRadius(dp(radius));return b;}
    private void add(LinearLayout parent,View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(top),0,dp(bottom));parent.addView(view,p);}
    private void divider(LinearLayout parent){View line=new View(this);line.setBackgroundColor(LINE);parent.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));}
    private int dp(float n){return (int)(getResources().getDisplayMetrics().density*n+.5f);}
    private final class Orbit extends View {
        final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);boolean connected,busy;
        Orbit(){super(MainActivity.this);setContentDescription("Connection status indicator");}
        @Override protected void onDraw(Canvas c){
            float x=getWidth()/2f,y=getHeight()/2f,r=dp(69);
            p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(1));p.setColor(LINE);c.drawCircle(x,y,r+dp(12),p);
            p.setStrokeWidth(dp(5));p.setColor(connected?GREEN:0xffd7dcd0);c.drawCircle(x,y,r,p);
            p.setColor(connected?GREEN:INK);p.setStrokeWidth(dp(4));p.setStrokeCap(Paint.Cap.ROUND);
            c.drawArc(x-dp(23),y-dp(23),x+dp(23),y+dp(23),-45,270,false,p);
            c.drawLine(x,y,x+dp(24),y,p);
            p.setStyle(Paint.Style.FILL);p.setColor(connected?0xffb5ce73:busy?0xffc6a360:LINE);c.drawCircle(x+r,y,dp(7),p);
            setContentDescription(connected?"Connected":busy?"Connection in progress":"Offline");
        }
    }
}
