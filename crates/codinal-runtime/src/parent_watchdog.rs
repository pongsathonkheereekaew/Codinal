//! Event-driven desktop-parent lifetime guard for the bundled runtime.

use std::ffi::OsStr;
use std::io;

pub const PARENT_PID_ENV: &str = "CODINAL_PARENT_PID";

fn parse_parent_pid(value: Option<&OsStr>) -> io::Result<Option<u32>> {
    let Some(value) = value else {
        return Ok(None);
    };
    let value = value.to_str().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "runtime parent PID is not UTF-8",
        )
    })?;
    let pid = value.parse::<u32>().map_err(|_| {
        io::Error::new(io::ErrorKind::InvalidInput, "runtime parent PID is invalid")
    })?;
    if pid <= 1 || pid > i32::MAX as u32 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "runtime parent PID is outside the supported range",
        ));
    }
    Ok(Some(pid))
}

pub fn start_from_environment() -> io::Result<()> {
    let Some(parent_pid) = parse_parent_pid(std::env::var_os(PARENT_PID_ENV).as_deref())? else {
        return Ok(());
    };
    start_parent_watchdog(parent_pid)
}

#[cfg(target_os = "macos")]
fn start_parent_watchdog(parent_pid: u32) -> io::Result<()> {
    use std::mem::MaybeUninit;
    use std::ptr;
    use std::thread;

    let expected_parent = parent_pid as libc::pid_t;
    if unsafe { libc::getppid() } != expected_parent {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "runtime desktop parent is no longer alive",
        ));
    }
    let queue = unsafe { libc::kqueue() };
    if queue < 0 {
        return Err(io::Error::last_os_error());
    }
    let change = libc::kevent {
        ident: parent_pid as libc::uintptr_t,
        filter: libc::EVFILT_PROC,
        flags: libc::EV_ADD | libc::EV_ENABLE | libc::EV_ONESHOT,
        fflags: libc::NOTE_EXIT,
        data: 0,
        udata: ptr::null_mut(),
    };
    if unsafe { libc::kevent(queue, &change, 1, ptr::null_mut(), 0, ptr::null()) } < 0 {
        let error = io::Error::last_os_error();
        unsafe { libc::close(queue) };
        return Err(error);
    }
    if unsafe { libc::getppid() } != expected_parent {
        unsafe { libc::close(queue) };
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "runtime desktop parent exited during watchdog setup",
        ));
    }
    thread::Builder::new()
        .name("codinal-parent-watchdog".to_owned())
        .spawn(move || {
            let mut event = MaybeUninit::<libc::kevent>::zeroed();
            loop {
                let observed = unsafe {
                    libc::kevent(queue, ptr::null(), 0, event.as_mut_ptr(), 1, ptr::null())
                };
                if observed > 0 {
                    unsafe { libc::close(queue) };
                    std::process::exit(0);
                }
                if observed < 0 && io::Error::last_os_error().kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                unsafe { libc::close(queue) };
                break;
            }
        })
        .map(|_| ())
        .inspect_err(|_| {
            unsafe { libc::close(queue) };
        })
}

#[cfg(not(target_os = "macos"))]
fn start_parent_watchdog(_parent_pid: u32) -> io::Result<()> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::parse_parent_pid;
    use std::ffi::OsStr;

    #[test]
    fn parent_pid_is_optional_but_strict_when_present() {
        assert_eq!(parse_parent_pid(None).expect("missing parent"), None);
        assert_eq!(
            parse_parent_pid(Some(OsStr::new("42"))).expect("valid parent"),
            Some(42)
        );
        assert!(parse_parent_pid(Some(OsStr::new("1"))).is_err());
        assert!(parse_parent_pid(Some(OsStr::new("not-a-pid"))).is_err());
    }
}
