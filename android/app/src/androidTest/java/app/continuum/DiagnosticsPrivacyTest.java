package app.continuum;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class DiagnosticsPrivacyTest {
    @Test public void exportedReportNeverContainsExceptionCredentialsOrEndpoint(){
        String secret="private-credential-6729",host="private-endpoint.invalid";
        Diagnostics.failure(new Exception("dns lookup https://"+secret+"@"+host));
        VpnStatus status=new VpnStatus("Connected","secret detail "+secret,host,"VLESS","WebSocket",10,0,0,true,true,true);
        String report=Diagnostics.report(status);
        assertTrue(report.contains("DNS-related"));assertFalse(report.contains(secret));assertFalse(report.contains(host));assertFalse(report.contains("secret detail"));
    }
    @Test public void packagedRustJniHandlesWideTokensAndClassifications(){
        long token=RustCore.start(1L<<42);assertTrue(token>(1L<<42));assertTrue(RustCore.accepts(token,token));assertFalse(RustCore.accepts(RustCore.stop(token),token));
        assertEquals(2,RustCore.classify(2));assertEquals(900,RustCore.fetchBackoff(30,60));
        Diagnostics.failure(new Exception("x509 certificate rejected"));assertTrue(Diagnostics.report(VpnStatus.offline()).contains("TLS/certificate-related"));
    }
}
