package app.continuum;

/** Allowlisted product copy. Never render backend errors, addresses or profiles. */
public final class ConnectionCopy {
    private ConnectionCopy(){}
    public static String title(String state){
        if("Connected".equals(state))return "You're connected.";
        if("Disconnecting".equals(state))return "Finishing up…";
        if("Waiting for network".equals(state))return "Waiting for internet.";
        if("Reconnecting".equals(state))return "Let's try again.";
        if("Checking connection".equals(state)||"Checking update".equals(state))return "Checking your connection.";
        if("Offline".equals(state)||"Disconnected".equals(state))return "A little more peace of mind.";
        return "Getting you connected…";
    }
    public static String detail(String state,boolean running){
        if(!running)return "Connect when you need it. Disconnect whenever you're done.";
        if("Connected".equals(state))return "Your connection is ready. You can leave this screen and carry on.";
        if("Disconnecting".equals(state))return "Closing your connection and pausing automatic recovery.";
        if("Waiting for network".equals(state))return "Check your Wi-Fi or mobile data. We'll try again when you're online.";
        return "This can take a moment. You can stop at any time.";
    }
}
