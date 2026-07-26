use codinal_desktop::oauth::parse_oauth_deep_link;
use url::Url;

const STATE: &str = "oauth-state-token-with-at-least-32-chars";

#[test]
fn parses_authorization_code_callback() {
    let url = Url::parse(&format!(
        "codinal://oauth/callback?flow=provider%3Aopenai&state={STATE}&code=secret-code"
    ))
    .unwrap();

    let callback = parse_oauth_deep_link(&url).unwrap();

    assert_eq!(callback.flow(), "provider:openai");
    assert_eq!(callback.state(), STATE);
    assert_eq!(callback.code(), "secret-code");
    assert!(callback.error().is_empty());
}

#[test]
fn parses_provider_error_callback() {
    let url = Url::parse(&format!(
        "codinal://oauth/callback?flow=provider%3Aopenai&state={STATE}&error=access_denied"
    ))
    .unwrap();

    let callback = parse_oauth_deep_link(&url).unwrap();

    assert_eq!(callback.error(), "access_denied");
    assert!(callback.code().is_empty());
}

#[test]
fn rejects_wrong_route_fragment_duplicates_unknowns_and_ambiguous_results() {
    let invalid = [
        format!("https://oauth/callback?flow=f&state={STATE}&code=x"),
        format!("codinal://other/callback?flow=f&state={STATE}&code=x"),
        format!("codinal://oauth/wrong?flow=f&state={STATE}&code=x"),
        format!("codinal://oauth/callback?flow=f&state={STATE}&code=x#secret"),
        format!("codinal://oauth/callback?flow=f&state={STATE}&state={STATE}&code=x"),
        format!("codinal://oauth/callback?flow=f&state={STATE}&code=x&extra=y"),
        format!("codinal://oauth/callback?flow=f&state={STATE}&code=x&error=no"),
        format!("codinal://oauth/callback?flow=f&state={STATE}"),
    ];

    for value in invalid {
        let url = Url::parse(&value).unwrap();
        assert!(parse_oauth_deep_link(&url).is_err(), "{value}");
    }
}

#[test]
fn rejects_invalid_flow_state_and_oversized_values_without_echoing_them() {
    let secret = "must-not-appear-in-errors";
    let invalid = [
        format!("codinal://oauth/callback?flow=bad%2Fflow&state={STATE}&code={secret}"),
        format!("codinal://oauth/callback?flow=f&state=too-short&code={secret}"),
        format!(
            "codinal://oauth/callback?flow=f&state={STATE}&code={}",
            "x".repeat(8193)
        ),
    ];

    for value in invalid {
        let url = Url::parse(&value).unwrap();
        let error = parse_oauth_deep_link(&url).err().unwrap().to_string();
        assert_eq!(error, "invalid OAuth callback");
        assert!(!error.contains(secret));
    }
}
