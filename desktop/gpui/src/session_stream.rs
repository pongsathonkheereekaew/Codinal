use codinal_control_plane_client::{ControlPlaneClient, PendingApproval};
use std::io;
use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};
use tungstenite::client::{client_with_config, IntoClientRequest};
use tungstenite::handshake::HandshakeError;
use tungstenite::http::header::{self, HeaderValue};
use tungstenite::protocol::WebSocketConfig;
use tungstenite::stream::MaybeTlsStream;
use tungstenite::{Error as WebSocketError, Message, WebSocket};

const UPDATE_QUEUE_CAPACITY: usize = 64;
const CONNECT_TIMEOUT: Duration = Duration::from_millis(500);
const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(1);
const SOCKET_POLL_INTERVAL: Duration = Duration::from_millis(250);
const MAX_RECONNECT_DELAY: Duration = Duration::from_secs(8);
const MAX_EVENT_MESSAGE_BYTES: usize = 256 * 1_024;

#[derive(Debug)]
pub enum SessionStreamUpdate {
    Connecting,
    StartFailed(String),
    HandshakeFailed(String),
    Connected,
    Event {
        raw: Vec<u8>,
        pending: Option<Result<Vec<PendingApproval>, String>>,
    },
    Closed,
    Disconnected(String),
    ConnectionFailed(String),
}

pub struct SessionStreamWorker {
    stop: Arc<AtomicBool>,
}

impl Drop for SessionStreamWorker {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
    }
}

pub fn spawn_session_stream(
    client: Arc<ControlPlaneClient>,
    session_id: String,
) -> io::Result<(SessionStreamWorker, Receiver<SessionStreamUpdate>)> {
    let (sender, receiver) = sync_channel(UPDATE_QUEUE_CAPACITY);
    let stop = Arc::new(AtomicBool::new(false));
    let thread_stop = Arc::clone(&stop);
    thread::Builder::new()
        .name("codinal-session-stream".to_owned())
        .spawn(move || run_session_stream(client, session_id, sender, thread_stop))
        .map_err(|error| io::Error::other(format!("could not start session stream: {error}")))?;
    Ok((SessionStreamWorker { stop }, receiver))
}

fn run_session_stream(
    client: Arc<ControlPlaneClient>,
    session_id: String,
    sender: SyncSender<SessionStreamUpdate>,
    stop: Arc<AtomicBool>,
) {
    let mut reconnect_delay = Duration::from_millis(250);
    while !stop.load(Ordering::Acquire) {
        if !send_update(&sender, SessionStreamUpdate::Connecting) {
            return;
        }
        let stream = match client.session_events(&session_id) {
            Ok(stream) => stream,
            Err(error) => {
                if !send_update(&sender, SessionStreamUpdate::StartFailed(error.to_string())) {
                    return;
                }
                if wait_for_retry(&stop, reconnect_delay) {
                    return;
                }
                reconnect_delay = next_reconnect_delay(reconnect_delay);
                continue;
            }
        };
        let mut request = match stream.url().into_client_request() {
            Ok(request) => request,
            Err(error) => {
                if !send_update(
                    &sender,
                    SessionStreamUpdate::HandshakeFailed(error.to_string()),
                ) {
                    return;
                }
                if wait_for_retry(&stop, reconnect_delay) {
                    return;
                }
                reconnect_delay = next_reconnect_delay(reconnect_delay);
                continue;
            }
        };
        let protocol_header = stream.subprotocols().join(", ");
        let protocol_header = match HeaderValue::from_str(&protocol_header) {
            Ok(value) => value,
            Err(error) => {
                if !send_update(
                    &sender,
                    SessionStreamUpdate::HandshakeFailed(error.to_string()),
                ) {
                    return;
                }
                if wait_for_retry(&stop, reconnect_delay) {
                    return;
                }
                reconnect_delay = next_reconnect_delay(reconnect_delay);
                continue;
            }
        };
        request
            .headers_mut()
            .insert(header::SEC_WEBSOCKET_PROTOCOL, protocol_header);

        match connect_session_socket(request) {
            Ok(mut socket) => {
                if let Err(error) = configure_socket(&mut socket) {
                    if !send_update(
                        &sender,
                        SessionStreamUpdate::ConnectionFailed(error.to_string()),
                    ) {
                        return;
                    }
                } else {
                    reconnect_delay = Duration::from_millis(250);
                    if !send_update(&sender, SessionStreamUpdate::Connected) {
                        return;
                    }
                    read_socket(&mut socket, &client, &session_id, &sender, &stop);
                }
            }
            Err(error) => {
                if !send_update(&sender, SessionStreamUpdate::ConnectionFailed(error)) {
                    return;
                }
            }
        }
        if wait_for_retry(&stop, reconnect_delay) {
            return;
        }
        reconnect_delay = next_reconnect_delay(reconnect_delay);
    }
}

fn connect_session_socket(
    request: tungstenite::handshake::client::Request,
) -> Result<WebSocket<MaybeTlsStream<TcpStream>>, String> {
    let uri = request.uri();
    if uri.scheme_str() != Some("ws") || uri.host() != Some("127.0.0.1") {
        return Err("session event stream must target local ws://127.0.0.1".to_owned());
    }
    let port = uri
        .port_u16()
        .ok_or_else(|| "session event stream requires an explicit port".to_owned())?;
    let address = SocketAddr::V4(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port));
    let stream = TcpStream::connect_timeout(&address, CONNECT_TIMEOUT)
        .map_err(|error| format!("session stream connect failed: {error}"))?;
    stream
        .set_read_timeout(Some(HANDSHAKE_TIMEOUT))
        .map_err(|error| format!("session stream handshake timeout failed: {error}"))?;
    stream
        .set_write_timeout(Some(HANDSHAKE_TIMEOUT))
        .map_err(|error| format!("session stream handshake timeout failed: {error}"))?;
    stream
        .set_nodelay(true)
        .map_err(|error| format!("session stream socket setup failed: {error}"))?;
    let config = WebSocketConfig::default()
        .read_buffer_size(16 * 1_024)
        .write_buffer_size(16 * 1_024)
        .max_write_buffer_size(512 * 1_024)
        .max_message_size(Some(MAX_EVENT_MESSAGE_BYTES))
        .max_frame_size(Some(MAX_EVENT_MESSAGE_BYTES));
    client_with_config(request, MaybeTlsStream::Plain(stream), Some(config))
        .map(|(socket, _response)| socket)
        .map_err(|error| match error {
            HandshakeError::Failure(error) => error.to_string(),
            HandshakeError::Interrupted(_) => "session stream handshake interrupted".to_owned(),
        })
}

fn configure_socket(socket: &mut WebSocket<MaybeTlsStream<TcpStream>>) -> io::Result<()> {
    #[allow(unreachable_patterns)]
    let stream = match socket.get_mut() {
        MaybeTlsStream::Plain(stream) => stream,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                "session event stream must use the local unencrypted transport",
            ));
        }
    };
    stream.set_read_timeout(Some(SOCKET_POLL_INTERVAL))?;
    stream.set_write_timeout(Some(SOCKET_POLL_INTERVAL))
}

fn read_socket(
    socket: &mut WebSocket<MaybeTlsStream<TcpStream>>,
    client: &ControlPlaneClient,
    session_id: &str,
    sender: &SyncSender<SessionStreamUpdate>,
    stop: &AtomicBool,
) {
    while !stop.load(Ordering::Acquire) {
        let raw = match socket.read() {
            Ok(Message::Text(raw)) => raw.as_slice().to_vec(),
            Ok(Message::Binary(raw)) => raw.as_slice().to_vec(),
            Ok(Message::Ping(payload)) => {
                if let Err(error) = socket.send(Message::Pong(payload)) {
                    let _ =
                        send_update(sender, SessionStreamUpdate::Disconnected(error.to_string()));
                    return;
                }
                continue;
            }
            Ok(Message::Close(_)) => {
                let _ = send_update(sender, SessionStreamUpdate::Closed);
                return;
            }
            Ok(_) => continue,
            Err(WebSocketError::Io(error))
                if matches!(
                    error.kind(),
                    io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
                ) =>
            {
                continue;
            }
            Err(error) => {
                let _ = send_update(sender, SessionStreamUpdate::Disconnected(error.to_string()));
                return;
            }
        };
        let pending = event_requires_approval(&raw).then(|| {
            client
                .pending_approvals(session_id)
                .map_err(|error| error.to_string())
        });
        if !send_update(sender, SessionStreamUpdate::Event { raw, pending }) {
            return;
        }
    }
}

fn event_requires_approval(raw: &[u8]) -> bool {
    serde_json::from_slice::<serde_json::Value>(raw)
        .ok()
        .and_then(|event| event.get("type")?.as_str().map(str::to_owned))
        .as_deref()
        == Some("permission_required")
}

fn send_update(sender: &SyncSender<SessionStreamUpdate>, update: SessionStreamUpdate) -> bool {
    sender.send(update).is_ok()
}

fn wait_for_retry(stop: &AtomicBool, delay: Duration) -> bool {
    let deadline = Instant::now() + delay;
    while !stop.load(Ordering::Acquire) {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return false;
        }
        thread::sleep(remaining.min(Duration::from_millis(50)));
    }
    true
}

fn next_reconnect_delay(current: Duration) -> Duration {
    std::cmp::min(current.saturating_mul(2), MAX_RECONNECT_DELAY)
}

#[cfg(test)]
mod tests {
    use super::{spawn_session_stream, SessionStreamUpdate};
    use codinal_control_plane_client::ControlPlaneClient;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::mpsc::sync_channel;
    use std::sync::Arc;
    use std::thread;
    use std::time::{Duration, Instant};

    const TOKEN: &str = "0123456789abcdef0123456789abcdef";

    #[test]
    #[allow(clippy::result_large_err)]
    fn worker_spawn_returns_before_idle_socket_closes() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let (release_sender, release_receiver) = sync_channel(1);
        let server = thread::spawn(move || {
            let (stream, _) = listener.accept().expect("connection");
            let mut socket = tungstenite::accept_hdr(
                stream,
                |_request: &tungstenite::handshake::server::Request,
                 mut response: tungstenite::handshake::server::Response| {
                    response.headers_mut().insert(
                        tungstenite::http::header::SEC_WEBSOCKET_PROTOCOL,
                        tungstenite::http::HeaderValue::from_static("codinal.v1"),
                    );
                    Ok(response)
                },
            )
            .expect("websocket handshake");
            let _ = release_receiver.recv_timeout(Duration::from_secs(2));
            let _ = socket.close(None);
        });

        let client = Arc::new(ControlPlaneClient::new(port, TOKEN).expect("client"));
        let started = Instant::now();
        let (worker, updates) =
            spawn_session_stream(client, "session-1".to_owned()).expect("stream worker");
        assert!(
            started.elapsed() < Duration::from_millis(100),
            "spawning an idle stream must not block the UI caller"
        );
        assert!(matches!(
            updates.recv_timeout(Duration::from_secs(1)),
            Ok(SessionStreamUpdate::Connecting)
        ));
        let connected = updates.recv_timeout(Duration::from_secs(1));
        assert!(
            matches!(connected, Ok(SessionStreamUpdate::Connected)),
            "expected connected update, got {connected:?}"
        );

        drop(worker);
        let _ = release_sender.send(());
        server.join().expect("server");
    }

    #[test]
    fn authenticated_stream_does_not_follow_redirects() {
        let redirect_target = TcpListener::bind("127.0.0.1:0").expect("redirect target");
        redirect_target
            .set_nonblocking(true)
            .expect("nonblocking redirect target");
        let target_port = redirect_target.local_addr().expect("target address").port();
        let (target_sender, target_receiver) = sync_channel(1);
        let target_server = thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_secs(1);
            while Instant::now() < deadline {
                match redirect_target.accept() {
                    Ok((mut stream, _)) => {
                        let _ = stream.set_read_timeout(Some(Duration::from_millis(250)));
                        let mut request = [0_u8; 4_096];
                        let read = stream.read(&mut request).unwrap_or(0);
                        let _ = target_sender
                            .send(String::from_utf8_lossy(&request[..read]).into_owned());
                        let _ = stream
                            .write_all(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n");
                        return;
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(10));
                    }
                    Err(_) => return,
                }
            }
        });

        let redirect_source = TcpListener::bind("127.0.0.1:0").expect("redirect source");
        let source_port = redirect_source.local_addr().expect("source address").port();
        let source_server = thread::spawn(move || {
            let (mut stream, _) = redirect_source.accept().expect("source connection");
            let _ = stream.set_read_timeout(Some(Duration::from_millis(250)));
            let mut request = [0_u8; 4_096];
            let _ = stream.read(&mut request);
            write!(
                stream,
                "HTTP/1.1 302 Found\r\nLocation: ws://127.0.0.1:{target_port}/capture\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .expect("redirect response");
        });

        let client = Arc::new(ControlPlaneClient::new(source_port, TOKEN).expect("client"));
        let (worker, updates) =
            spawn_session_stream(client, "session-redirect".to_owned()).expect("stream worker");
        assert!(matches!(
            updates.recv_timeout(Duration::from_secs(1)),
            Ok(SessionStreamUpdate::Connecting)
        ));
        let _ = updates.recv_timeout(Duration::from_secs(1));
        let redirected = target_receiver
            .recv_timeout(Duration::from_millis(100))
            .is_ok();

        drop(worker);
        source_server.join().expect("source server");
        target_server.join().expect("target server");
        assert!(!redirected, "authenticated WebSocket followed a redirect");
    }

    #[test]
    fn stalled_handshake_is_bounded() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (_stream, _) = listener.accept().expect("connection");
            thread::sleep(Duration::from_secs(2));
        });

        let client = Arc::new(ControlPlaneClient::new(port, TOKEN).expect("client"));
        let (worker, updates) =
            spawn_session_stream(client, "stalled-handshake".to_owned()).expect("stream worker");
        assert!(matches!(
            updates.recv_timeout(Duration::from_secs(1)),
            Ok(SessionStreamUpdate::Connecting)
        ));
        let failure = updates.recv_timeout(Duration::from_millis(1_500));
        assert!(
            matches!(failure, Ok(SessionStreamUpdate::ConnectionFailed(_))),
            "stalled handshake was not bounded: {failure:?}"
        );

        drop(worker);
        server.join().expect("server");
    }

    #[test]
    #[allow(clippy::result_large_err)]
    fn oversized_event_is_rejected_before_queueing() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener");
        let port = listener.local_addr().expect("address").port();
        let server = thread::spawn(move || {
            let (stream, _) = listener.accept().expect("connection");
            let mut socket = tungstenite::accept_hdr(
                stream,
                |_request: &tungstenite::handshake::server::Request,
                 mut response: tungstenite::handshake::server::Response| {
                    response.headers_mut().insert(
                        tungstenite::http::header::SEC_WEBSOCKET_PROTOCOL,
                        tungstenite::http::HeaderValue::from_static("codinal.v1"),
                    );
                    Ok(response)
                },
            )
            .expect("websocket handshake");
            let _ = socket.send(tungstenite::Message::Binary(vec![0_u8; 300 * 1_024].into()));
        });

        let client = Arc::new(ControlPlaneClient::new(port, TOKEN).expect("client"));
        let (worker, updates) =
            spawn_session_stream(client, "oversized-event".to_owned()).expect("stream worker");
        assert!(matches!(
            updates.recv_timeout(Duration::from_secs(1)),
            Ok(SessionStreamUpdate::Connecting)
        ));
        assert!(matches!(
            updates.recv_timeout(Duration::from_secs(1)),
            Ok(SessionStreamUpdate::Connected)
        ));
        let rejected = updates.recv_timeout(Duration::from_secs(1));
        assert!(
            matches!(rejected, Ok(SessionStreamUpdate::Disconnected(_))),
            "oversized event reached the UI queue: {rejected:?}"
        );

        drop(worker);
        server.join().expect("server");
    }
}
