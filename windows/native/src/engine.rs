use serde_json::Value;
use std::{io::{Read, Write}, net::{TcpListener,TcpStream}, os::windows::process::CommandExt, os::windows::io::AsRawHandle, process::{Child,Command,Stdio}, ptr::null_mut, time::{Duration,Instant}};
use windows_sys::Win32::{Foundation::CloseHandle, System::JobObjects::*};
use crate::profile;

pub struct Engine { child: Child, job: isize, pub port: u16 }
impl Engine {
    pub fn start(outbound: &Value, scoped: bool) -> Result<Self, ()> {
        let listener=TcpListener::bind("127.0.0.1:0").map_err(|_|())?;
        let port=listener.local_addr().map_err(|_|())?.port(); drop(listener);
        let binary=std::env::current_exe().map_err(|_|())?.parent().ok_or(())?.join("engine/xray.exe");
        // Never persist a connection secret to disk or display engine output.
        let mut child=Command::new(binary).args(["run","-config","stdin:"]).creation_flags(0x08000000)
            .stdin(Stdio::piped()).stdout(Stdio::null()).stderr(Stdio::null()).spawn().map_err(|_|())?;
        let job=unsafe { CreateJobObjectW(null_mut(),std::ptr::null()) };
        let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION=unsafe { std::mem::zeroed() };
        limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let guarded=unsafe { !job.is_null() && SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits as *const _ as _,std::mem::size_of_val(&limits) as u32)!=0 && AssignProcessToJobObject(job,child.as_raw_handle())!=0 };
        if !guarded { let _=child.kill();let _=child.wait();if !job.is_null(){unsafe{CloseHandle(job);}}return Err(()); }
        let mut result=Self{child,job:job as isize,port};
        let mut input=result.child.stdin.take().ok_or(())?;
        input.write_all(profile::config(outbound,port,scoped).to_string().as_bytes()).map_err(|_|())?;drop(input);
        for _ in 0..100 {
            if !result.running(){return Err(());}
            if TcpStream::connect_timeout(&format!("127.0.0.1:{port}").parse().unwrap(),Duration::from_millis(100)).is_ok(){return Ok(result);}
            std::thread::sleep(Duration::from_millis(100));
        }
        Err(())
    }
    pub fn running(&mut self)->bool { matches!(self.child.try_wait(),Ok(None)) }
    pub fn health(&self)->Result<u128,()> {
        let proxy=reqwest::Proxy::all(format!("http://127.0.0.1:{}",self.port)).map_err(|_|())?;
        let client=reqwest::blocking::Client::builder().proxy(proxy).timeout(Duration::from_secs(6)).redirect(reqwest::redirect::Policy::none()).build().map_err(|_|())?;
        for url in ["https://www.gstatic.com/generate_204","https://www.cloudflare.com/cdn-cgi/trace"] {
            let start=Instant::now();
            if client.get(url).send().map_or(false,|r|r.status().is_success()){return Ok(start.elapsed().as_millis());}
        } Err(())
    }
}
impl Drop for Engine {fn drop(&mut self){let _=self.child.kill();let _=self.child.wait();unsafe {CloseHandle(self.job as _);}}}
pub fn fetch()->Result<Value,()> {
    let client=reqwest::blocking::Client::builder().no_proxy().https_only(true).timeout(Duration::from_secs(15)).redirect(reqwest::redirect::Policy::limited(5)).user_agent("Continuum/0.3").build().map_err(|_|())?;
    let response=client.get(profile::SOURCE).send().map_err(|_|())?.error_for_status().map_err(|_|())?;
    let mut data=String::new();response.take(65537).read_to_string(&mut data).map_err(|_|())?;
    profile::parse(&data)
}
