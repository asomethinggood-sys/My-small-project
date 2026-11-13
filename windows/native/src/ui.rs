use crate::{Action,Status};
use std::{ptr::{null,null_mut},sync::{Arc,Mutex,mpsc::Sender}};
use windows_sys::Win32::{Foundation::*,Graphics::Gdi::*,System::LibraryLoader::GetModuleHandleW,UI::WindowsAndMessaging::*};
fn wide(s:&str)->Vec<u16>{s.encode_utf16().chain(Some(0)).collect()}
struct Ui {state:Arc<Mutex<Status>>,tx:Sender<Action>,title:HWND,detail:HWND,button:HWND,time:HWND,check:HWND,fonts:Vec<HFONT>,paper:HBRUSH}
unsafe fn label(parent:HWND,text:&str,x:i32,y:i32,w:i32,h:i32,font:HFONT)->HWND{
    let control=CreateWindowExW(0,wide("STATIC").as_ptr(),wide(text).as_ptr(),WS_CHILD|WS_VISIBLE,x,y,w,h,parent,null_mut(),GetModuleHandleW(null()),null());
    SendMessageW(control,WM_SETFONT,font as usize,1);control
}
unsafe fn button(parent:HWND,text:&str,id:usize,x:i32,y:i32,w:i32,font:HFONT)->HWND{
    let control=CreateWindowExW(0,wide("BUTTON").as_ptr(),wide(text).as_ptr(),WS_CHILD|WS_VISIBLE|WS_TABSTOP,x,y,w,46,parent,id as HMENU,GetModuleHandleW(null()),null());
    SendMessageW(control,WM_SETFONT,font as usize,1);control
}
unsafe fn font(size:i32,name:&str)->HFONT{CreateFontW(-size,0,0,0,400,0,0,0,DEFAULT_CHARSET as u32,0,0,CLEARTYPE_QUALITY as u32,0,wide(name).as_ptr())}
unsafe fn set(hwnd:HWND,s:&str){SetWindowTextW(hwnd,wide(s).as_ptr());}
unsafe extern "system" fn procedure(hwnd:HWND,msg:u32,w:WPARAM,l:LPARAM)->LRESULT{
    let ptr=GetWindowLongPtrW(hwnd,GWLP_USERDATA) as *mut Ui;
    match msg {
        WM_NCCREATE=>{let create=&*(l as *const CREATESTRUCTW);SetWindowLongPtrW(hwnd,GWLP_USERDATA,create.lpCreateParams as isize);return DefWindowProcW(hwnd,msg,w,l);},
        WM_CTLCOLORSTATIC=>{if !ptr.is_null(){SetTextColor(w as HDC,0x00343c24);SetBkColor(w as HDC,0x00eef4f6);return (*ptr).paper as isize;}},
        WM_ERASEBKGND=>{if !ptr.is_null(){let mut r=std::mem::zeroed();GetClientRect(hwnd,&mut r);FillRect(w as HDC,&r,(*ptr).paper);return 1;}},
        WM_TIMER=>{if !ptr.is_null(){let ui=&mut *ptr;let s=ui.state.lock().unwrap().clone();set(ui.title,&s.title);set(ui.detail,&s.detail);set(ui.button,if s.wanted{"Disconnect"}else{"Connect"});set(ui.time,&format!("{:02}:{:02}:{:02}",s.elapsed/3600,s.elapsed/60%60,s.elapsed%60));set(ui.check,&s.latency.map(|v|format!("{v} ms")).unwrap_or("—".into()));}return 0;},
        WM_COMMAND=>{if !ptr.is_null(){let ui=&mut *ptr;match w&0xffff{
            1=>{let wanted=ui.state.lock().unwrap().wanted;let mut s=ui.state.lock().unwrap();s.wanted=!wanted;s.title=if wanted{"Finishing up…"}else{"Getting you connected…"}.into();s.detail=if wanted{"Closing your connection. This may take a few seconds."}else{"This can take a moment. You can stop at any time."}.into();drop(s);let _=ui.tx.send(if wanted{Action::Disconnect}else{Action::Connect});},
            2=>{let _=ui.tx.send(Action::Check);},
            3=>{MessageBoxW(hwnd,wide("Continuum routes your device's internet connection while connected. The network service handling your connection may process connection information.\n\nA VPN does not make you anonymous. Websites can still identify you through accounts and cookies. No advertising or analytics SDK is included.\n\nDisconnect stops automatic recovery. Closing this app disconnects. This is not an always-on kill switch.").as_ptr(),wide("Your connection, your choice").as_ptr(),MB_OK);},_=>{}}}return 0;},
        WM_CLOSE=>{if !ptr.is_null(){let _=(*ptr).tx.send(Action::Exit);}DestroyWindow(hwnd);return 0;},
        WM_DESTROY=>{KillTimer(hwnd,1);PostQuitMessage(0);return 0;},_=>{}
    }
    DefWindowProcW(hwnd,msg,w,l)
}
pub fn show(state:Arc<Mutex<Status>>,tx:Sender<Action>){unsafe{
    SetProcessDPIAware();
    let mutex=windows_sys::Win32::System::Threading::CreateMutexW(null(),0,wide("Local\\Continuum.Managed.Desktop").as_ptr());
    if GetLastError()==ERROR_ALREADY_EXISTS {MessageBoxW(null_mut(),wide("Continuum is already open.").as_ptr(),wide("Continuum").as_ptr(),MB_OK);if !mutex.is_null(){CloseHandle(mutex);}return;}
    let paper=CreateSolidBrush(0x00eef4f6);let fonts=vec![font(26,"Segoe UI"),font(34,"Georgia"),font(16,"Segoe UI"),font(25,"Segoe UI")];
    let mut ui=Box::new(Ui{state,tx,title:null_mut(),detail:null_mut(),button:null_mut(),time:null_mut(),check:null_mut(),fonts,paper});
    let instance=GetModuleHandleW(null());let class=wide("ContinuumConsumer");
    let wc=WNDCLASSW{lpfnWndProc:Some(procedure),hInstance:instance,lpszClassName:class.as_ptr(),hCursor:LoadCursorW(null_mut(),IDC_ARROW),hbrBackground:paper,..std::mem::zeroed()};RegisterClassW(&wc);
    let hwnd=CreateWindowExW(0,class.as_ptr(),wide("Continuum").as_ptr(),WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,510,690,null_mut(),null_mut(),instance,&mut *ui as *mut _ as _);
    if hwnd.is_null(){CloseHandle(mutex);return;}
    label(hwnd,"continuum",30,25,420,40,ui.fonts[0]);
    ui.title=label(hwnd,"A little more peace of mind.",30,105,438,96,ui.fonts[1]);
    ui.detail=label(hwnd,"Connect when you need it. Disconnect whenever you're done.",30,218,438,72,ui.fonts[2]);
    ui.button=button(hwnd,"Connect",1,30,306,438,ui.fonts[2]);
    label(hwnd,"One tap. No setup needed.",30,366,438,26,ui.fonts[2]);
    label(hwnd,"Your connection",30,417,438,28,ui.fonts[2]);
    ui.time=label(hwnd,"00:00:00",30,458,210,36,ui.fonts[3]);ui.check=label(hwnd,"—",260,458,200,36,ui.fonts[3]);
    label(hwnd,"Time connected",30,500,210,24,ui.fonts[2]);label(hwnd,"Web request · not ping",260,500,210,24,ui.fonts[2]);
    button(hwnd,"Check connection",2,30,550,260,ui.fonts[2]);button(hwnd,"Privacy",3,310,550,158,ui.fonts[2]);
    label(hwnd,"Closing this app disconnects your connection.",30,614,438,24,ui.fonts[2]);
    SetTimer(hwnd,1,500,None);ShowWindow(hwnd,SW_SHOW);UpdateWindow(hwnd);
    let mut msg:MSG=std::mem::zeroed();while GetMessageW(&mut msg,null_mut(),0,0)>0{if IsDialogMessageW(hwnd,&msg)==0{TranslateMessage(&msg);DispatchMessageW(&msg);}}
    for f in &ui.fonts{DeleteObject(*f);}DeleteObject(paper);if !mutex.is_null(){CloseHandle(mutex);}
}}
