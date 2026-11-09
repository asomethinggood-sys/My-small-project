//! Dependency-free policy and counters. JNI takes primitives only; no retained
//! pointers, dereferenced Java objects, or panics cross the JNI boundary.
mod nyx;
use std::ffi::c_void;
use std::sync::atomic::{AtomicI64, Ordering};
static METRICS: [AtomicI64; 4] = [AtomicI64::new(0),AtomicI64::new(0),AtomicI64::new(0),AtomicI64::new(0)];
pub fn health_seconds(interactive: bool) -> i32 { if interactive {300} else {900} }
pub fn next_seconds(manual: bool, requested: i32, interactive: bool) -> i32 {
    if manual {return health_seconds(interactive);}
    let valid=if requested==30 || requested==120 {requested} else {60};
    if interactive {valid} else {valid.max(120)}
}
pub fn health_due(now:i64,last:i64,forced:bool,interactive:bool)->bool {
    forced || last<=0 || now<last || now.saturating_sub(last)>=i64::from(health_seconds(interactive))*1000
}
pub fn start(state:i64)->i64 {state.wrapping_add(2)|1}
pub fn stop(state:i64)->i64 {state.wrapping_add(2)&!1}
pub fn accepts(state:i64,token:i64)->bool {state&1!=0 && state==token}
pub fn fetch_backoff(failures:i32,normal:i32)->i32 {
    let base=normal.clamp(30,120);
    if failures<=0 {base} else {base.saturating_mul(1_i32<<failures.clamp(1,5)).min(900)}
}
pub fn network_changed(previous:i64,next:i64)->bool {previous!=next}
pub fn reuse_validator(source:bool,resource:bool,body:bool)->bool {source && resource && body}
pub fn classify(mask:i32)->i32 {if mask&1!=0 {1} else if mask&2!=0 {2} else if mask&4!=0 {3} else if mask&8!=0 {4} else {0}}
fn add_metric(index:i32,value:i64) {
    if let Some(counter)=METRICS.get(index as usize) {
        let _=counter.fetch_update(Ordering::Relaxed,Ordering::Relaxed,|old|Some(old.saturating_add(value.max(0))));
    }
}
fn metric(index:i32)->i64 {METRICS.get(index as usize).map(|v|v.load(Ordering::Relaxed)).unwrap_or(-1)}
type Env=*mut c_void;type Class=*mut c_void;
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_healthSeconds(_:Env,_:Class,i:u8)->i32 {health_seconds(i!=0)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_nextSeconds(_:Env,_:Class,m:u8,r:i32,i:u8)->i32 {next_seconds(m!=0,r,i!=0)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_healthDue(_:Env,_:Class,n:i64,l:i64,f:u8,i:u8)->u8 {health_due(n,l,f!=0,i!=0) as u8}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_start(_:Env,_:Class,s:i64)->i64 {start(s)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_stop(_:Env,_:Class,s:i64)->i64 {stop(s)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_accepts(_:Env,_:Class,s:i64,t:i64)->u8 {accepts(s,t) as u8}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_fetchBackoff(_:Env,_:Class,f:i32,n:i32)->i32 {fetch_backoff(f,n)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_networkChanged(_:Env,_:Class,p:i64,n:i64)->u8 {network_changed(p,n) as u8}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_reuseValidator(_:Env,_:Class,s:u8,r:u8,b:u8)->u8 {reuse_validator(s!=0,r!=0,b!=0) as u8}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_addMetric(_:Env,_:Class,i:i32,v:i64) {add_metric(i,v)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_metric(_:Env,_:Class,i:i32)->i64 {metric(i)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_classify(_:Env,_:Class,m:i32)->i32 {classify(m)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_exitEligibility(_:Env,_:Class,n:i64,g:i64,e:i64,v:i32,f:i32)->i32 {nyx::eligibility(n,g,e,v,f)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_connectionPhase(_:Env,_:Class,r:u8,t:u8,e:u8,v:u8,s:u8)->i32 {nyx::phase(r!=0,t!=0,e!=0,v!=0,s!=0)}
#[no_mangle]
pub extern "system" fn Java_app_continuum_RustCore_motionProgress(_:Env,_:Class,e:i64,d:i64,r:u8)->i32 {nyx::motion(e,d,r!=0)}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn manual_idle(){assert_eq!(next_seconds(true,30,false),900);assert_eq!(next_seconds(true,120,true),300);}
    #[test] fn background_subscription(){assert_eq!(next_seconds(false,30,false),120);assert_eq!(next_seconds(false,30,true),30);}
    #[test] fn malformed_interval(){assert_eq!(next_seconds(false,i32::MIN,true),60);}
    #[test] fn forced_health(){assert!(health_due(2,1,true,false));assert!(!health_due(2,1,false,false));}
    #[test] fn clock_edges(){assert!(health_due(i64::MAX,1,false,false));assert!(health_due(1,2,false,true));}
    #[test] fn generations(){let first=start(0);assert!(accepts(first,first));let stopped=stop(first);assert!(!accepts(stopped,first));let next=start(stopped);assert!(!accepts(next,first));assert!(accepts(next,next));}
    #[test] fn stopped_token(){let s=stop(start(0));assert!(!accepts(s,s));}
    #[test] fn wrap_defined(){let s=start(i64::MAX);assert!(accepts(s,s));assert!(!accepts(stop(s),s));}
    #[test] fn bounded_backoff(){assert_eq!(fetch_backoff(0,60),60);assert_eq!(fetch_backoff(1,60),120);assert_eq!(fetch_backoff(i32::MAX,60),900);assert_eq!(fetch_backoff(-2,-5),30);}
    #[test] fn unchanged_network(){assert!(!network_changed(12,12));assert!(network_changed(12,-1));}
    #[test] fn validators(){assert!(reuse_validator(true,true,true));assert!(!reuse_validator(true,false,true));assert!(!reuse_validator(false,true,true));assert!(!reuse_validator(true,true,false));}
    #[test] fn diagnostic_priority(){assert_eq!(classify(0),0);assert_eq!(classify(5),1);assert_eq!(classify(6),2);assert_eq!(classify(4),3);assert_eq!(classify(8),4);}
    #[test] fn counters_reject_bad_index(){add_metric(-1,10);assert_eq!(metric(-1),-1);add_metric(100,10);assert_eq!(metric(100),-1);}
}
