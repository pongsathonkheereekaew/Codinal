use std::fs;
use std::io::{Read, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::process::{Child, Command};
use std::thread;
use std::time::Duration;

const TOKEN: &str = "0123456789abcdef0123456789abcdef";

struct RuntimeProcess(Child);

impl Drop for RuntimeProcess {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[test]
fn runtime_keeps_serving_after_a_malformed_loopback_connection() {
    let data_dir = std::env::temp_dir().join(format!(
        "codinal-runtime-bootstrap-test-{}",
        std::process::id()
    ));
    let _ = fs::remove_dir_all(&data_dir);
    fs::create_dir(&data_dir).expect("data directory");
    let port = TcpListener::bind("127.0.0.1:0")
        .expect("port listener")
        .local_addr()
        .expect("address")
        .port();
    let mut command = Command::new(env!("CARGO_BIN_EXE_codinal-runtime"));
    command
        .env("CODINAL_SESSION_TOKEN", TOKEN)
        .env("CODINAL_PORT", port.to_string())
        .env("CODINAL_DATA_DIR", &data_dir);
    let process = RuntimeProcess(command.spawn().expect("runtime process"));

    let mut malformed = connect_when_ready(port);
    malformed
        .write_all(b"GET /v1/health HTTP/1.1\r\n")
        .expect("malformed request");
    malformed.shutdown(Shutdown::Write).expect("close request");
    thread::sleep(Duration::from_millis(50));

    let mut healthy = connect_when_ready(port);
    healthy
        .write_all(
            format!(
                "GET /v1/health HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
            )
            .as_bytes(),
        )
        .expect("health request");
    let mut response = String::new();
    healthy
        .read_to_string(&mut response)
        .expect("health response");
    assert!(response.starts_with("HTTP/1.1 200 OK\r\n"));

    drop(process);
    fs::remove_dir_all(data_dir).expect("remove data directory");
}

fn connect_when_ready(port: u16) -> TcpStream {
    for _ in 0..50 {
        if let Ok(stream) = TcpStream::connect(("127.0.0.1", port)) {
            return stream;
        }
        thread::sleep(Duration::from_millis(10));
    }
    panic!("runtime did not start");
}
