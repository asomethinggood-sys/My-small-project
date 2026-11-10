package app.continuum;
import org.junit.Test;
import static org.junit.Assert.*;
public class CheckPolicyTest {
    @Test public void manualProfilesDoNotPollEveryMinute(){assertEquals(300,CheckPolicy.nextSeconds(true,30,true));assertEquals(900,CheckPolicy.nextSeconds(true,30,false));}
    @Test public void screenOffCoalescesSubscriptionChecks(){assertEquals(120,CheckPolicy.nextSeconds(false,30,false));assertEquals(120,CheckPolicy.nextSeconds(false,120,false));assertEquals(30,CheckPolicy.nextSeconds(false,30,true));}
    @Test public void manualRefreshAndNetworkChangeBypassHealthCache(){assertTrue(CheckPolicy.healthDue(101,100,true,false));assertFalse(CheckPolicy.healthDue(101,100,false,false));assertTrue(CheckPolicy.healthDue(900100,100,false,false));}
    @Test public void initialHealthNeverSkippedAndInvalidIntervalBounded(){assertTrue(CheckPolicy.healthDue(1,0,false,true));assertEquals(60,CheckPolicy.nextSeconds(false,-1,true));assertEquals(120,CheckPolicy.offlineSeconds());}
}
