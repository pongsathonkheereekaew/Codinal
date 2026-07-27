use std::collections::HashMap;
use std::io;
use std::sync::Mutex;

use codinal_desktop::secrets::{
    encode_secret_bootstrap, provider_secret_status, update_provider_secret, SecretVault,
};

const SYNC_TOKEN: &str = "test-secret-sync-token-with-at-least-32-chars";

#[derive(Default)]
struct FakeVault {
    values: HashMap<String, String>,
    base_urls: HashMap<String, String>,
}

impl SecretVault for FakeVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        Ok(self.values.get(provider).cloned())
    }

    fn set(&self, _provider: &str, _value: &str) -> io::Result<()> {
        unreachable!("not used by this test")
    }

    fn delete(&self, _provider: &str) -> io::Result<bool> {
        unreachable!("not used by this test")
    }

    fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
        Ok(self.base_urls.get(provider).cloned())
    }
}

#[test]
fn bootstrap_contains_only_supported_configured_providers() {
    let vault = FakeVault {
        values: HashMap::from([
            ("openai".to_owned(), "openai-secret".to_owned()),
            ("unknown".to_owned(), "must-not-appear".to_owned()),
        ]),
        base_urls: HashMap::new(),
    };

    let payload = encode_secret_bootstrap(&vault, SYNC_TOKEN).expect("bootstrap");
    let document: serde_json::Value = serde_json::from_slice(&payload).expect("valid JSON");

    assert_eq!(
        document,
        serde_json::json!({
            "sync_token": SYNC_TOKEN,
            "profiles": {
                "provider:openai": {"api_key": "openai-secret"}
            }
        })
    );
    assert!(!String::from_utf8_lossy(&payload).contains("must-not-appear"));
}

#[test]
fn status_never_contains_secret_values() {
    let vault = FakeVault {
        values: HashMap::from([
            ("anthropic".to_owned(), "anthropic-secret".to_owned()),
            ("gemini".to_owned(), "gemini-secret".to_owned()),
        ]),
        base_urls: HashMap::new(),
    };

    let status = provider_secret_status(&vault).expect("status");
    let serialized = serde_json::to_string(&status).expect("JSON status");

    assert_eq!(
        serialized,
        r#"[{"provider":"anthropic","configured":true},{"provider":"gemini","configured":true},{"provider":"openai","configured":false},{"provider":"zai","configured":false},{"provider":"deepseek","configured":false},{"provider":"omniroute","configured":false},{"provider":"github","configured":false}]"#
    );
    assert!(!serialized.contains("anthropic-secret"));
    assert!(!serialized.contains("gemini-secret"));
}

#[derive(Default)]
struct MutableVault {
    values: Mutex<HashMap<String, String>>,
    base_urls: Mutex<HashMap<String, String>>,
}

impl SecretVault for MutableVault {
    fn get(&self, provider: &str) -> io::Result<Option<String>> {
        Ok(self.values.lock().expect("lock").get(provider).cloned())
    }

    fn set(&self, provider: &str, value: &str) -> io::Result<()> {
        self.values
            .lock()
            .expect("lock")
            .insert(provider.to_owned(), value.to_owned());
        Ok(())
    }

    fn delete(&self, provider: &str) -> io::Result<bool> {
        Ok(self.values.lock().expect("lock").remove(provider).is_some())
    }

    fn get_base_url(&self, provider: &str) -> io::Result<Option<String>> {
        Ok(self.base_urls.lock().expect("lock").get(provider).cloned())
    }

    fn set_base_url(&self, provider: &str, value: Option<&str>) -> io::Result<()> {
        let mut store = self.base_urls.lock().expect("lock");
        match value {
            Some(text) if !text.is_empty() => {
                store.insert(provider.to_owned(), text.to_owned());
            }
            _ => {
                store.remove(provider);
            }
        }
        Ok(())
    }
}

#[test]
fn failed_runtime_sync_rolls_back_keychain_change() {
    let vault = MutableVault {
        values: Mutex::new(HashMap::from([(
            "openai".to_owned(),
            "old-secret".to_owned(),
        )])),
        base_urls: Mutex::new(HashMap::new()),
    };

    let error = update_provider_secret(&vault, "openai", Some("new-secret"), None, || {
        Err(io::Error::other("runtime unavailable"))
    })
    .expect_err("sync fails");

    assert_eq!(error.to_string(), "runtime unavailable");
    assert_eq!(
        vault.get("openai").expect("vault read"),
        Some("old-secret".to_owned())
    );
}

#[test]
fn omniroute_base_url_round_trips_through_bootstrap() {
    let vault = FakeVault {
        values: HashMap::from([("omniroute".to_owned(), "omni-key".to_owned())]),
        base_urls: HashMap::from([(
            "omniroute".to_owned(),
            "http://localhost:20128/v1".to_owned(),
        )]),
    };

    let payload = encode_secret_bootstrap(&vault, SYNC_TOKEN).expect("bootstrap");
    let document: serde_json::Value = serde_json::from_slice(&payload).expect("valid JSON");

    assert_eq!(
        document,
        serde_json::json!({
            "sync_token": SYNC_TOKEN,
            "profiles": {
                "provider:omniroute": {
                    "api_key": "omni-key",
                    "base_url": "http://localhost:20128/v1"
                }
            }
        })
    );
}

#[test]
fn update_rejects_base_url_for_provider_that_does_not_accept_it() {
    let vault = MutableVault::default();
    let error = update_provider_secret(&vault, "openai", Some("k"), Some("http://x/v1"), || Ok(()))
        .expect_err("openai rejects base_url");
    assert!(error.to_string().contains("base_url"));
}
