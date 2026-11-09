package app.continuum;

/** Monotonic-clock scheduling policy. No alarms, wake locks or synthetic ping figures. */
public final class CheckPolicy {
    private CheckPolicy(){}
    public static int healthSeconds(boolean interactive){return interactive?300:900;}
    public static int nextSeconds(boolean manual,int requested,boolean interactive){
        if(manual)return healthSeconds(interactive);
        int valid=requested==30||requested==120?requested:60;
        return interactive?valid:Math.max(valid,120);
    }
    public static boolean healthDue(long now,long last,boolean forced,boolean interactive){
        return forced||last==0||now-last>=healthSeconds(interactive)*1000L;
    }
    public static int offlineSeconds(){return 120;}
}
