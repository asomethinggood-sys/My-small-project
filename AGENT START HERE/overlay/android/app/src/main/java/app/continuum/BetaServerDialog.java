package app.continuum;

import android.app.*;
import android.os.Handler;
import android.os.Looper;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import go.Seq;
import libv2ray.Libv2ray;
import org.json.JSONObject;

/** Display-only server labels and measured HTTPS timings, never profiles/URLs. */
public final class BetaServerDialog {
    private static final ExecutorService scan=Executors.newSingleThreadExecutor();
    private static final BetaPool pool=new BetaPool();
    private static final AtomicBoolean busy=new AtomicBoolean();
    private static boolean initialized;
    private BetaServerDialog(){}
    public static void show(Activity activity,SettingsStore store,Runnable connect){
        LinearLayout content=new LinearLayout(activity);content.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*activity.getResources().getDisplayMetrics().density);content.setPadding(pad,pad,pad,pad);
        TextView intro=new TextView(activity);intro.setText("OPEN BETA · Choose automatically or pick a preferred server. If it fails, another available server may be used. Switching can interrupt calls.\n\nLatency is a full HTTPS request, not ICMP ping.");content.addView(intro);
        TextView selected=new TextView(activity);int preference=store.load().optInt("betaSlot",0);selected.setText(preference==0?"Preferred: Automatic":"Preferred: "+BetaCatalog.label(preference));content.addView(selected);
        Button automatic=new Button(activity);automatic.setAllCaps(false);automatic.setText("Automatic · best measured server");content.addView(automatic);
        Button check=new Button(activity);check.setAllCaps(false);check.setText("Check all servers");content.addView(check);
        TextView[] timings=new TextView[BetaCatalog.COUNT];Button[] choices=new Button[BetaCatalog.COUNT];
        for(int i=0;i<BetaCatalog.COUNT;i++){
            final int slot=i+1;LinearLayout row=new LinearLayout(activity);row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            TextView label=new TextView(activity);label.setText(BetaCatalog.label(slot));row.addView(label,new LinearLayout.LayoutParams(0,-2,1));
            timings[i]=new TextView(activity);timings[i].setText("Not checked");row.addView(timings[i]);
            choices[i]=new Button(activity);choices[i].setAllCaps(false);choices[i].setText("Connect");choices[i].setEnabled(false);row.addView(choices[i]);content.addView(row);
        }
        ScrollView scroll=new ScrollView(activity);scroll.addView(content);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Servers").setView(scroll).setNegativeButton("Close",null).create();
        java.util.function.IntConsumer choose=slot->{try{JSONObject settings=store.load();settings.put("betaSlot",slot);store.save(settings);dialog.dismiss();connect.run();}catch(Exception ignored){Toast.makeText(activity,"Couldn't save your selection. Try again.",Toast.LENGTH_SHORT).show();}};
        automatic.setOnClickListener(v->choose.accept(0));
        for(int i=0;i<choices.length;i++){final int slot=i+1;choices[i].setOnClickListener(v->choose.accept(slot));}
        check.setOnClickListener(v->{
            if(!busy.compareAndSet(false,true)){Toast.makeText(activity,"A server check is already running.",Toast.LENGTH_SHORT).show();return;}
            check.setEnabled(false);check.setText("Checking…");for(int i=0;i<timings.length;i++){timings[i].setText("Checking…");choices[i].setEnabled(false);}
            android.content.Context context=activity.getApplicationContext();
            scan.execute(()->{
                List<BetaCatalog.Result> results=new ArrayList<>();
                try{
                    if(!initialized){Seq.setContext(context);Libv2ray.initCoreEnv(context.getFilesDir().getAbsolutePath(),"");initialized=true;}
                    results=pool.refresh(entry->{
                        for(String url:new String[]{TunnelService.TEST_URL,"https://cp.cloudflare.com/generate_204"}){
                            try{long ms=Libv2ray.measureOutboundDelay(Profile.parse(entry.uri).config(false).toString(),url);if(ms>=0)return ms;}catch(Exception ignored){}
                        }return -1;
                    },true);
                }catch(Exception|LinkageError ignored){}finally{busy.set(false);}
                final List<BetaCatalog.Result> ready=results;
                new Handler(Looper.getMainLooper()).post(()->{
                    if(activity.isFinishing()||activity.isDestroyed()||!dialog.isShowing())return;
                    for(int i=0;i<timings.length;i++)timings[i].setText("Unavailable");
                    for(BetaCatalog.Result result:ready){int index=result.entry.slot-1;boolean fresh=result.entry.valid(System.currentTimeMillis()/1000);timings[index].setText(fresh&&result.latency>=0?result.latency+" ms":"Not responding");choices[index].setEnabled(fresh&&result.latency>=0);}
                    check.setText("Check all servers");check.setEnabled(true);
                });
            });
        });dialog.show();
    }
}
