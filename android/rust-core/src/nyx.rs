//! Fail-closed catalog policy and connection presentation. No sockets or secrets.
/// 0 unavailable, 1 metadata only, 2 expired, 3 blocked, 4 usable.
/// All times are epoch seconds. A catalog cannot authorize shared use itself.
pub fn eligibility(now: i64, generated: i64, expires: i64, verified: i32, flags: i32) -> i32 {
    if now <= 0 || generated <= 0 || generated > now || expires <= generated
        || expires.saturating_sub(generated) > 900 || now >= expires { return 2; }
    if verified <= 0 { return if flags & 1 != 0 { 1 } else { 0 }; }
    // Shared-use approval, authenticated API, fresh full-path evidence and UDP.
    if flags & 30 != 30 { return 3; }
    4
}
/// Presentation may never show Connected solely because an operation was started.
pub fn phase(running: bool, tun: bool, engine: bool, verified: bool, stopping: bool) -> i32 {
    if stopping { 3 } else if !running { 0 } else if tun && engine && verified { 2 } else { 1 }
}
/// Bounded smoothstep interpolation in integer parts per thousand. Shared across UI.
pub fn motion(elapsed: i64, duration: i64, reduced: bool) -> i32 {
    if reduced || duration <= 0 { return 1000; }
    let x = ((elapsed.clamp(0, duration) as f64) / duration as f64).clamp(0.0, 1.0);
    (x * x * (3.0 - 2.0 * x) * 1000.0).round() as i32
}
/// 0 keep, 1 renew, 2 block. Monotonic milliseconds, no wall-clock leases.
pub fn lease_action(now: i64, deadline: i64, same_selection: bool) -> i32 {
    if !same_selection || now < 0 || deadline <= now || deadline.saturating_sub(now) > 300_000 { return 2; }
    if deadline - now <= 30_000 { 1 } else { 0 }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn lease_boundaries() { assert_eq!(lease_action(100,30100,true),1); assert_eq!(lease_action(100,30101,true),0); assert_eq!(lease_action(100,100,true),2); assert_eq!(lease_action(100,99,true),2); assert_eq!(lease_action(100,300101,true),2); assert_eq!(lease_action(100,200,false),2); assert_eq!(lease_action(-1,200,true),2); }
    #[test] fn no_counts_without_evidence() { assert_eq!(eligibility(100,90,190,0,31),1); assert_eq!(eligibility(100,90,190,0,0),0); }
    #[test] fn all_gates_required() { for flag in [0,2,4,8,16,14,22,26,28] { assert_eq!(eligibility(100,90,190,1,flag),3); } assert_eq!(eligibility(100,90,190,1,30),4); }
    #[test] fn stale_future_and_long_lived_rejected() { for (g,e) in [(101,200),(90,100),(90,991),(0,100), (90,89)] { assert_eq!(eligibility(100,g,e,1,31),2); } }
    #[test] fn negative_and_overflow() { assert_eq!(eligibility(-1,1,10,1,31),2); assert_eq!(eligibility(100,1,i64::MAX,1,31),2); }
    #[test] fn phase_requires_all_resources() { assert_eq!(phase(true,true,true,true,false),2); for (t,e,v) in [(false,true,true),(true,false,true),(true,true,false)] { assert_eq!(phase(true,t,e,v,false),1); } assert_eq!(phase(false,true,true,true,false),0); assert_eq!(phase(true,true,true,true,true),3); }
    #[test] fn motion_is_monotonic_and_bounded() { let mut last=0; for t in -10..1100 { let v=motion(t,1000,false); assert!(v>=last && v<=1000); last=v; } assert_eq!(motion(500,1000,false),500); }
    #[test] fn motion_respects_reduced_setting() { assert_eq!(motion(0,400,true),1000); assert_eq!(motion(0,0,false),1000); assert_eq!(motion(i64::MAX,400,false),1000); }
}
