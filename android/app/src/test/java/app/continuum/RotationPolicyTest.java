package app.continuum;
import org.junit.Test;
import static org.junit.Assert.*;
public class RotationPolicyTest {
    @Test public void healthyUnchangedDoesNotRestart(){Profile p=Profile.parse(ProfileTest.URI);assertEquals(RotationPolicy.Decision.KEEP,RotationPolicy.decide(p,p,true,true));}
    @Test public void unverifiedChangeDoesNotReplaceActive(){
        Profile old=Profile.parse(ProfileTest.URI), next=Profile.parse(ProfileTest.URI.replace("one.trycloudflare","two.trycloudflare"));
        assertEquals(RotationPolicy.Decision.REJECT,RotationPolicy.decide(old,next,false,true));
        assertEquals(RotationPolicy.Decision.INSTALL,RotationPolicy.decide(old,next,true,true));
    }
    @Test public void stoppedCoreRequiresVerification(){Profile p=Profile.parse(ProfileTest.URI);assertEquals(RotationPolicy.Decision.REJECT,RotationPolicy.decide(p,p,false,false));assertEquals(RotationPolicy.Decision.INSTALL,RotationPolicy.decide(p,p,true,false));}
    @Test public void retryIsBounded(){assertEquals(5,RotationPolicy.retrySeconds(1));assertEquals(10,RotationPolicy.retrySeconds(2));assertEquals(60,RotationPolicy.retrySeconds(999));}
}
