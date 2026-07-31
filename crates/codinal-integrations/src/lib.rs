//! Bounded declarative integration manifest validation.

use serde_json::Value;

const MAX_BYTES: usize = 8 * 1024;
const ALLOWED: &[&str] = &["schema", "id", "version", "publisher", "agents", "skills", "mcp", "providers"];

pub fn validate_manifest(bytes: &[u8]) -> Result<Value, &'static str> {
    if bytes.len() > MAX_BYTES { return Err("manifest too large"); }
    let value: Value = serde_json::from_slice(bytes).map_err(|_| "invalid manifest JSON")?;
    let object = value.as_object().ok_or("manifest must be an object")?;
    if object.get("schema").and_then(Value::as_str) != Some("codinal.integration.v1") { return Err("unsupported manifest schema"); }
    if object.keys().any(|key| !ALLOWED.contains(&key.as_str())) { return Err("manifest contains executable or unsupported fields"); }
    for key in ["id", "version", "publisher"] {
        if object.get(key).and_then(Value::as_str).filter(|value| !value.is_empty() && value.len() <= 128).is_none() { return Err("manifest identity is invalid"); }
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::validate_manifest;

    #[test]
    fn accepts_bounded_declarative_v1_manifest() {
        assert!(validate_manifest(br#"{"schema":"codinal.integration.v1","id":"acme/demo","version":"1","publisher":"acme","skills":[]}"#).is_ok());
    }

    #[test]
    fn rejects_executable_assets() {
        assert!(validate_manifest(br#"{"schema":"codinal.integration.v1","id":"acme/demo","version":"1","publisher":"acme","script":"curl bad"}"#).is_err());
    }
}
