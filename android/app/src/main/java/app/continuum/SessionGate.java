package app.continuum;

/** Every asynchronous result belongs to one session. Stop invalidates all outstanding work. */
public final class SessionGate {
    private long generation;
    private boolean active;
    public synchronized long start() {active=true;return ++generation;}
    public synchronized void stop() {active=false;++generation;}
    public synchronized boolean accepts(long token) {return active && generation==token;}
    public synchronized boolean active() {return active;}
    public synchronized long current() {return generation;}
}
