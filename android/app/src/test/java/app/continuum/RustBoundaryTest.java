package app.continuum;
import org.junit.Test;
import static org.junit.Assert.*;
public class RustBoundaryTest {
    @Test public void realNativeLibraryMatchesJavaPrimitiveAbi(){assertEquals(900,RustCore.healthSeconds(false));assertEquals(30,RustCore.nextSeconds(false,30,true));assertTrue(RustCore.healthDue(Long.MAX_VALUE,1,false,true));}
    @Test public void longGenerationIsNotTruncated(){long token=RustCore.start(1L<<40);assertTrue(token>(1L<<40));assertTrue(RustCore.accepts(token,token));assertFalse(RustCore.accepts(RustCore.stop(token),token));}
    @Test public void resourceChangesNeverReuseValidators(){assertTrue(RustCore.reuseValidator(true,true,true));assertFalse(RustCore.reuseValidator(true,false,true));assertFalse(RustCore.reuseValidator(false,true,true));assertFalse(RustCore.reuseValidator(true,true,false));}
    @Test public void backoffBoundedAndNetworkChangesDeduplicated(){assertEquals(900,RustCore.fetchBackoff(Integer.MAX_VALUE,60));assertFalse(RustCore.networkChanged(99,99));assertTrue(RustCore.networkChanged(99,100));}
    @Test public void telemetryUsesValidIndicesOnly(){assertEquals(-1,RustCore.metric(-1));RustCore.addMetric(-1,100);assertEquals(-1,RustCore.metric(-1));assertEquals(2,RustCore.classify(2));}
}
