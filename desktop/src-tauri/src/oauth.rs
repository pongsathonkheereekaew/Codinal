use std::io;

use url::Url;

const MAX_FLOW_LEN: usize = 128;
const MIN_STATE_LEN: usize = 32;
const MAX_STATE_LEN: usize = 256;
const MAX_CODE_LEN: usize = 8192;
const MAX_ERROR_LEN: usize = 256;

pub struct OAuthDeepLink {
    flow: String,
    state: String,
    code: String,
    error: String,
}

impl OAuthDeepLink {
    pub fn flow(&self) -> &str {
        &self.flow
    }

    pub fn state(&self) -> &str {
        &self.state
    }

    pub fn code(&self) -> &str {
        &self.code
    }

    pub fn error(&self) -> &str {
        &self.error
    }
}

impl Drop for OAuthDeepLink {
    fn drop(&mut self) {
        use zeroize::Zeroize;

        self.flow.zeroize();
        self.state.zeroize();
        self.code.zeroize();
        self.error.zeroize();
    }
}

pub fn parse_oauth_deep_link(url: &Url) -> io::Result<OAuthDeepLink> {
    if url.scheme() != "codinal"
        || url.host_str() != Some("oauth")
        || url.path() != "/callback"
        || !url.username().is_empty()
        || url.password().is_some()
        || url.port().is_some()
        || url.fragment().is_some()
    {
        return Err(invalid_callback());
    }

    let mut flow = None;
    let mut state = None;
    let mut code = None;
    let mut error = None;
    for (key, value) in url.query_pairs() {
        let slot = match key.as_ref() {
            "flow" => &mut flow,
            "state" => &mut state,
            "code" => &mut code,
            "error" => &mut error,
            _ => return Err(invalid_callback()),
        };
        if slot.replace(value.into_owned()).is_some() {
            return Err(invalid_callback());
        }
    }

    let flow = flow.ok_or_else(invalid_callback)?;
    let state = state.ok_or_else(invalid_callback)?;
    let code = code.unwrap_or_default();
    let error = error.unwrap_or_default();
    if !valid_flow(&flow)
        || !valid_state(&state)
        || (code.is_empty() == error.is_empty())
        || code.len() > MAX_CODE_LEN
        || error.len() > MAX_ERROR_LEN
    {
        return Err(invalid_callback());
    }
    Ok(OAuthDeepLink {
        flow,
        state,
        code,
        error,
    })
}

fn valid_flow(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_FLOW_LEN
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._:-".contains(&byte))
}

fn valid_state(value: &str) -> bool {
    (MIN_STATE_LEN..=MAX_STATE_LEN).contains(&value.len())
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn invalid_callback() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, "invalid OAuth callback")
}
