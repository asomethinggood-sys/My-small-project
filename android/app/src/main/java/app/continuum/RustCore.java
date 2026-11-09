package app.continuum;

/** Primitive-only JNI boundary. No silent Java fallback. R8 preserves this ABI. */
public final class RustCore {
    static {System.loadLibrary("continuum_core");}
    private RustCore(){}
    public static native int healthSeconds(boolean interactive);
    public static native int nextSeconds(boolean manual,int requested,boolean interactive);
    public static native boolean healthDue(long now,long last,boolean forced,boolean interactive);
    public static native long start(long state);
    public static native long stop(long state);
    public static native boolean accepts(long state,long token);
    public static native int fetchBackoff(int failures,int normal);
    public static native boolean networkChanged(long previous,long next);
    public static native boolean reuseValidator(boolean sameSource,boolean sameResource,boolean hasBody);
    public static native void addMetric(int index,long value);
    public static native long metric(int index);
    public static native int classify(int evidenceMask);
}
