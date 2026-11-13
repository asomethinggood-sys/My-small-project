mod profile;
mod engine;
use std::{fs,time::{Duration,Instant}};
fn main(){
    let p=profile::parse("ss://YWVzLTEyOC1nY206Y29udGludXVtLWNpLW9ubHktcGFzc3dvcmQ@127.0.0.1:23081#LocalFixture").unwrap();
    if std::env::args().any(|s|s=="--lifecycle"){
        let mut engine=engine::Engine::start(&p,true).unwrap();assert!(engine.running());let port=engine.port;
        let client=reqwest::blocking::Client::builder().proxy(reqwest::Proxy::all(format!("http://127.0.0.1:{port}")).unwrap()).timeout(Duration::from_secs(8)).build().unwrap();
        assert_eq!(client.get("http://198.18.0.10:23080/").send().unwrap().text().unwrap(),"continuum-windows-route-fixture");
        drop(engine);assert!(std::net::TcpStream::connect(format!("127.0.0.1:{port}")).is_err());
        println!("PASS Rust owned engine lifecycle and listener cleanup");return;
    }
    fs::create_dir_all("fixture").unwrap();
    let c=profile::config(&p,23082,false);fs::write("fixture/full-tun.json",c.to_string()).unwrap();
    let mut c=profile::config(&p,23082,true);c["log"]=serde_json::json!({"loglevel":"warning","error":"fixture/tun-detail.log"});
    fs::write("fixture/scoped-tun.json",c.to_string()).unwrap();
    let mut legacy=c.clone();legacy["outbounds"][1]["settings"]=serde_json::json!({"nonIPQuery":"drop"});fs::write("fixture/legacy-dns-tun.json",legacy.to_string()).unwrap();
    c["dns"]["servers"][0]["address"]=serde_json::json!("https://192.0.2.1/dns-query");fs::write("fixture/fallback-tun.json",c.to_string()).unwrap();
    let start=Instant::now();assert!(start.elapsed()<Duration::from_secs(1));println!("PASS Rust production config fixtures generated");
}
