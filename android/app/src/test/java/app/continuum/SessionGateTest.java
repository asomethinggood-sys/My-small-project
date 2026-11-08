package app.continuum;
import org.junit.Test;
import static org.junit.Assert.*;
public class SessionGateTest {
    @Test public void stopInvalidatesEveryOutstandingResult(){SessionGate g=new SessionGate();long t=g.start();assertTrue(g.accepts(t));g.stop();assertFalse(g.accepts(t));assertFalse(g.active());}
    @Test public void reconnectNeverAcceptsPreviousProbe(){SessionGate g=new SessionGate();long old=g.start();g.stop();long next=g.start();assertFalse(g.accepts(old));assertTrue(g.accepts(next));assertEquals(next,g.current());}
    @Test public void repeatedStopIsSafe(){SessionGate g=new SessionGate();g.stop();g.stop();assertFalse(g.active());assertTrue(g.accepts(g.start()));}
}
