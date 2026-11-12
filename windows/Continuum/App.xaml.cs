using System;
using System.Threading;
using System.Windows;

namespace Continuum;
public partial class App : Application
{
    Mutex? instance;
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        instance = new Mutex(true, @"Local\Continuum.Windows.Tunnel", out bool created);
        if (!created) { MessageBox.Show("Continuum is already open. Check the system tray.", "Continuum"); Shutdown(); return; }
        MainWindow = new MainWindow(); MainWindow.Show();
    }
    protected override void OnExit(ExitEventArgs e) { instance?.Dispose(); base.OnExit(e); }
}
