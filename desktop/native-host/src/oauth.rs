use std::io;

use url::Url;
use zeroize::Zeroizing;

const MAX_FLOW_LEN: usize = 128;
const MIN_STATE_LEN: usize = 32;
const MAX_STATE_LEN: usize = 256;
const MAX_CODE_LEN: usize = 8192;
const MAX_ERROR_LEN: usize = 256;

pub struct OAuthDeepLink {
    flow: Zeroizing<String>,
    state: Zeroizing<String>,
    code: Zeroizing<String>,
    error: Zeroizing<String>,
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
        if slot.replace(Zeroizing::new(value.into_owned())).is_some() {
            return Err(invalid_callback());
        }
    }

    let flow = flow.ok_or_else(invalid_callback)?;
    let state = state.ok_or_else(invalid_callback)?;
    let code = code.unwrap_or_else(|| Zeroizing::new(String::new()));
    let error = error.unwrap_or_else(|| Zeroizing::new(String::new()));
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_exact_callback_shape_and_redacts_through_accessors() {
        let state = "a".repeat(MIN_STATE_LEN);
        let url = Url::parse(&format!(
            "codinal://oauth/callback?flow=github&state={state}&code=secret-code"
        ))
        .unwrap();
        let callback = parse_oauth_deep_link(&url).unwrap();
        assert_eq!(callback.flow(), "github");
        assert_eq!(callback.state(), state);
        assert_eq!(callback.code(), "secret-code");
        assert!(callback.error().is_empty());
    }

    #[test]
    fn rejects_ambiguous_or_extended_callback_shapes() {
        let state = "b".repeat(MIN_STATE_LEN);
        for url in [
            format!("codinal://oauth/callback?flow=x&state={state}&code=a&error=b"),
            format!("codinal://oauth/callback?flow=x&state={state}&code=a&code=b"),
            format!("codinal://oauth/callback?flow=x&state={state}&code=a&extra=b"),
            format!("codinal://oauth/other?flow=x&state={state}&code=a"),
        ] {
            assert!(parse_oauth_deep_link(&Url::parse(&url).unwrap()).is_err());
        }
    }
}
