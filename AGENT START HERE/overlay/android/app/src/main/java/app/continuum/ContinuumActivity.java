package app.continuum;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.VpnService;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.util.Locale;

/** Consumer Continuum surface. Technical status stays inside the service. */
public final class ContinuumActivity extends Activity {
    static final int PAPER=0xfff6f4ee,INK=0xff243c34,MUTED=0xff69756e,ACCENT=0xff275d47,LINE=0xffdedfd6;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private StateClient client;private SettingsStore store;
    private TextView title,detail,pill,elapsed,check,footnote;
    private Button connect;
    private String lastState="";
    private final Runnable update=new Runnable(){public void run(){render();handler.postDelayed(this,1000);}};
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);client=new StateClient(this);store=new SettingsStore(this);
        if(BuildConfig.MANAGED_ONLY){try{store.save(store.load());}catch(Exception ignored){/* Save never changes the enforced read policy. */}}
        getWindow().setStatusBarColor(PAPER);getWindow().setNavigationBarColor(PAPER);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|(Build.VERSION.SDK_INT>=26?View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR:0));
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(PAPER);
        LinearLayout root=column();root.setPadding(dp(24),dp(20),dp(24),dp(24));scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(24),dp(12)+insets.getSystemWindowInsetTop(),dp(24),dp(24)+insets.getSystemWindowInsetBottom());return insets.consumeSystemWindowInsets();});
        LinearLayout header=row();TextView brand=text("continuum",25,INK);brand.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));Button settings=button("Settings",PAPER,INK);settings.setTag("settings");settings.setOnClickListener(v->ContinuumSettings.show(this,store,client));header.addView(settings);root.addView(header);
        pill=text("  ●  Not connected  ",12,MUTED);pill.setPadding(dp(10),dp(7),dp(10),dp(7));pill.setBackground(shape(0xffe9ece4,20));
        LinearLayout badge=row();badge.addView(pill);add(root,badge,30,20);
        title=text("A little more peace of mind.",36,INK);title.setTypeface(Typeface.create("serif",Typeface.NORMAL));title.setLineSpacing(dp(2),1);title.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);add(root,title,0,14);
        detail=text("Connect when you need it. Disconnect whenever you're done.",15,MUTED);detail.setLineSpacing(dp(4),1);detail.setMinHeight(dp(72));add(root,detail,0,22);
        connect=button("Connect",ACCENT,0xfff8faf5);connect.setTag("connect");connect.setTextSize(17);connect.setOnClickListener(v->toggle());root.addView(connect,new LinearLayout.LayoutParams(-1,dp(58)));
        TextView hint=text(BuildConfig.BETA_POOL?"1.0 OPEN BETA · Availability may change":"One tap. No setup needed.",12,MUTED);hint.setGravity(Gravity.CENTER);add(root,hint,10,12);
        if(BuildConfig.BETA_POOL){Button servers=button("Servers",PAPER,ACCENT);servers.setTag("servers");servers.setOnClickListener(v->BetaServerDialog.show(this,store,()->{if(client.status.running)client.refresh();else toggle();}));add(root,servers,0,20);}
        LinearLayout card=column();card.setPadding(dp(18),dp(18),dp(18),dp(18));card.setBackground(shape(0xffffffff,18));
        TextView heading=text("Your connection",15,INK);heading.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));card.addView(heading);
        LinearLayout metrics=row(),time=column(),response=column();elapsed=text("—",25,INK);elapsed.setFontFeatureSettings("tnum");time.addView(elapsed);time.addView(text("Time connected",12,MUTED));check=text("—",25,INK);check.setFontFeatureSettings("tnum");response.addView(check);response.addView(text("Connection check",12,MUTED));
        metrics.addView(time,new LinearLayout.LayoutParams(0,-2,1));metrics.addView(response,new LinearLayout.LayoutParams(0,-2,1));add(card,metrics,18,16);
        View line=new View(this);line.setBackgroundColor(LINE);card.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
        Button refresh=button("Check connection",0xffffffff,ACCENT);refresh.setTag("check");refresh.setOnClickListener(v->{if(client.status.running)client.refresh();else Toast.makeText(this,"Connect first, then try a check.",Toast.LENGTH_SHORT).show();});card.addView(refresh,new LinearLayout.LayoutParams(-1,dp(48)));root.addView(card);
        footnote=text("Connection checks measure a web request, not ping.",11,MUTED);footnote.setLineSpacing(dp(3),1);add(root,footnote,12,24);
        LinearLayout bottom=row();TextView note=text("You're in control.",13,INK);bottom.addView(note,new LinearLayout.LayoutParams(0,-2,1));Button privacy=button("Privacy",PAPER,ACCENT);privacy.setTag("privacy");privacy.setOnClickListener(v->privacy());bottom.addView(privacy);root.addView(bottom);
        add(root,text("Disconnect pauses recovery. Android's always-on VPN settings may keep internet access blocked while you're disconnected.",12,MUTED),4,0);
    }
    private void render(){
        VpnStatus s=client.status;
        boolean connected=s.running&&s.tunOpen&&s.engineRunning&&"Connected".equals(s.state);
        String visible=connected?"Connected":!s.running?"Offline":"Connected".equals(s.state)?"Checking connection":s.state;
        if(!visible.equals(lastState)){title.setText(ConnectionCopy.title(visible));detail.setText(ConnectionCopy.detail(visible,s.running));lastState=visible;}
        if(BuildConfig.BETA_POOL&&connected&&s.detail.matches("US🇺🇸_[0-9]{2}"))detail.setText("Connected to "+s.detail+". You can leave this screen and carry on.");
        pill.setText(connected?"  ●  Connected  ":s.running?"  ●  Connecting  ":"  ●  Not connected  ");pill.setTextColor(connected?ACCENT:MUTED);
        boolean stopping="Disconnecting".equals(s.state);connect.setText(stopping?"Disconnecting…":s.running?"Disconnect":"Connect");connect.setEnabled(!stopping);connect.setAlpha(stopping?.6f:1);
        long seconds=s.connectedAt==0?0:Math.max(0,(SystemClock.elapsedRealtime()-s.connectedAt)/1000);
        elapsed.setText(s.connectedAt==0?"—":String.format(Locale.US,"%02d:%02d:%02d",seconds/3600,(seconds/60)%60,seconds%60));
        check.setText(s.latency<0?"—":s.latency+" ms");
    }
    private void toggle(){if(client.status.running){client.disconnect();render();return;}Intent consent=VpnService.prepare(this);if(consent!=null)startActivityForResult(consent,10);else start();}
    private void start(){client.connect();render();if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==10&&result==RESULT_OK)start();}
    @Override protected void onResume(){super.onResume();client.begin();handler.post(update);}
    @Override protected void onPause(){handler.removeCallbacks(update);client.end();super.onPause();}
    private void privacy(){new AlertDialog.Builder(this).setTitle("Your connection, your choice")
        .setMessage("Continuum uses Android's VPN permission to route your connection. No advertising or analytics SDK is included.\n\nThe network service handling your connection may process connection information. A VPN does not make you anonymous, and websites can still identify you through accounts and cookies.\n\nDisconnect stops the connection and pauses recovery. Reconnecting can interrupt active downloads or calls.")
        .setPositiveButton("Got it",null).show();}
    LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);return v;}
    Button button(String s,int fill,int ink){Button b=new Button(this);b.setText(s);b.setAllCaps(false);b.setTextColor(ink);b.setTextSize(14);b.setMinHeight(dp(48));b.setPadding(dp(14),0,dp(14),0);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x18606060),shape(fill,16),null));return b;}
    GradientDrawable shape(int color,int radius){GradientDrawable b=new GradientDrawable();b.setColor(color);b.setCornerRadius(dp(radius));return b;}
    void add(LinearLayout parent,View child,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(top),0,dp(bottom));parent.addView(child,p);}
    int dp(float n){return (int)(getResources().getDisplayMetrics().density*n+.5f);}
}
