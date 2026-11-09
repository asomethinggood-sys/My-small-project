package app.continuum;

/** Android adapter. Scheduling decisions live in the Rust core. */
public final class CheckPolicy {
    private CheckPolicy(){}
    public static int healthSeconds(boolean interactive){return RustCore.healthSeconds(interactive);}
    public static int nextSeconds(boolean manual,int requested,boolean interactive){return RustCore.nextSeconds(manual,requested,interactive);}
    public static boolean healthDue(long now,long last,boolean forced,boolean interactive){return RustCore.healthDue(now,last,forced,interactive);}
    public static int offlineSeconds(){return 120;}
}
