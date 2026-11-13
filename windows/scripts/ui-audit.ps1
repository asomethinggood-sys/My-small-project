param([Parameter(Mandatory=$true)][IntPtr]$Window)
$ErrorActionPreference='Stop'
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class ConsumerUi {
 public delegate bool Callback(IntPtr hwnd, IntPtr data);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hwnd, Callback callback, IntPtr data);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hwnd,StringBuilder text,int count);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hwnd,StringBuilder text,int count);
 public static List<string> Read(IntPtr parent) {
  var result=new List<string>();
  EnumChildWindows(parent,(h,d)=>{var text=new StringBuilder(2048);var kind=new StringBuilder(256);GetWindowText(h,text,text.Capacity);GetClassName(h,kind,kind.Capacity);result.Add(kind.ToString()+": "+text.ToString());return true;},IntPtr.Zero);
  return result;
 }
}
'@
$text=[ConsumerUi]::Read($Window) -join "`n"
if ($text -notmatch 'continuum' -or $text -notmatch 'Connect' -or $text -notmatch 'Privacy') { throw 'Consumer controls missing' }
if ($text -match '(?i)github|asomethinggood|repository|subscription|xray|vless|vmess|trojan|https?://|import|^Edit:') { throw 'Technical details or editable configuration exposed' }
Write-Output '::notice title=Consumer UI audit::Native controls contain no repository, endpoint, protocol, source or import surface'
