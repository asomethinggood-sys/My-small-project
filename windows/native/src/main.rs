#![windows_subsystem = "windows"]
mod profile;
mod engine;
mod ui;
use std::{sync::{Arc,Mutex,mpsc}, time::{Duration,Instant}};
use engine::Engine;

#[derive(Clone)] pub struct Status { pub wanted:bool, pub title:String, pub detail:String, pub elapsed:u64, pub latency:Option<u128> }
impl Default for Status {fn default()->Self {Self{wanted:false,title:"A little more peace of mind.".into(),detail:"Connect when you need it. Disconnect whenever you're done.".into(),elapsed:0,latency:None}}}
pub enum Action {Connect,Disconnect,Check,Exit}
fn main(){
    // No source/profile arguments, environment overrides, persisted credentials,
    // custom configuration files or legacy imported settings are accepted.
    let status=Arc::new(Mutex::new(Status::default()));let (tx,rx)=mpsc::channel();
    let copy=status.clone();let worker=std::thread::spawn(move||run(rx,copy));
    ui::show(status,tx.clone());let _=tx.send(Action::Exit);let _=worker.join();
}
fn run(rx:mpsc::Receiver<Action>,status:Arc<Mutex<Status>>){
    let mut engine:Option<Engine>=None;let mut current=serde_json::Value::Null;let mut pending=serde_json::Value::Null;
    let mut wanted=false;let mut failures=0;let mut started=Instant::now();let mut poll=Instant::now();let mut fetched=Instant::now()-Duration::from_secs(301);
    loop {
        match rx.recv_timeout(Duration::from_millis(250)) {
            Ok(Action::Exit)|Err(mpsc::RecvTimeoutError::Disconnected)=>break,
            Ok(Action::Disconnect)=>{wanted=false;engine=None;current=serde_json::Value::Null;pending=serde_json::Value::Null;*status.lock().unwrap()=Status::default();continue;},
            Ok(Action::Connect)=>{wanted=true;poll=Instant::now();fetched=Instant::now()-Duration::from_secs(301);failures=0;let mut s=status.lock().unwrap();s.wanted=true;s.title="Getting you connected…".into();s.detail="This can take a moment. You can stop at any time.".into();},
            Ok(Action::Check)=>poll=Instant::now(),
            Err(mpsc::RecvTimeoutError::Timeout)=>{}
        }
        if !wanted {continue;}
        if engine.is_some(){status.lock().unwrap().elapsed=started.elapsed().as_secs();}
        if Instant::now()<poll{continue;}
        poll=Instant::now()+Duration::from_secs(30);
        if fetched.elapsed()>=Duration::from_secs(300)||engine.is_none(){
            fetched=Instant::now();if let Ok(next)=engine::fetch(){pending=next;}
        }
        // Drain requests made while bounded I/O was in flight before starting
        // another tunnel. A late fetch can never undo an explicit disconnect.
        let mut stop=false;let mut exit=false;
        while let Ok(action)=rx.try_recv(){match action{Action::Disconnect=>stop=true,Action::Exit=>{stop=true;exit=true;},_=>{}}}
        if exit{break;}if stop{wanted=false;engine=None;current=serde_json::Value::Null;pending=serde_json::Value::Null;*status.lock().unwrap()=Status::default();continue;}
        let running=engine.as_mut().map_or(false,Engine::running);
        if !pending.is_null() && profile::replace(running,failures,&current,&pending){
            engine=None;
            match Engine::start(&pending,false){Ok(e)=>{engine=Some(e);current=pending.clone();started=Instant::now();failures=0;},Err(())=>{}}
        }
        let health=engine.as_ref().map(Engine::health).unwrap_or(Err(()));
        let mut s=status.lock().unwrap();s.wanted=true;
        match health {Ok(ms)=>{failures=0;s.latency=Some(ms);s.title="You're connected.".into();s.detail="Your connection is ready. Leave this window open and carry on.".into();},Err(())=>{
            failures+=1;s.latency=None;
            if engine.as_mut().map_or(false,Engine::running){s.title="Connection check unavailable.".into();s.detail="Your connection is still open. A failed check won't interrupt an active call.".into();}
            else{s.title="Waiting for a connection.".into();s.detail="Check your internet access. We'll try again shortly.".into();poll=Instant::now()+Duration::from_secs(30);}
        }}
    }
    drop(engine);
}
