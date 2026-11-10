package app.continuum;

/** The monitor serializes JNI transitions; Rust owns token semantics. No native heap handles. */
public final class SessionGate {
    private long state;
    public synchronized long start(){state=RustCore.start(state);return state;}
    public synchronized void stop(){state=RustCore.stop(state);}
    public synchronized boolean accepts(long token){return RustCore.accepts(state,token);}
    public synchronized boolean active(){return RustCore.accepts(state,state);}
    public synchronized long current(){return state;}
}
