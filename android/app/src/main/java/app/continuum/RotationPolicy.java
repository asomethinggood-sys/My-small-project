package app.continuum;

/** Testable decision layer; no automatic restart when only the URI label changes. */
public final class RotationPolicy {
    public enum Decision { KEEP, INSTALL, REJECT }
    public static Decision decide(Profile active, Profile candidate, boolean candidateVerified, boolean coreRunning) {
        if (active!=null && active.key().equals(candidate.key()) && coreRunning) return Decision.KEEP;
        return candidateVerified ? Decision.INSTALL : Decision.REJECT;
    }
    public static int retrySeconds(int failures) { return Math.min(60, 5 << Math.min(4,Math.max(0,failures-1))); }
}
