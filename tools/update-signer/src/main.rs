use base64::Engine as _;
use minisign::{sign, SecretKey, SecretKeyBox};
use std::env;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::PathBuf;
use zeroize::Zeroizing;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut arguments = env::args_os().skip(1);
    let secret_key = PathBuf::from(arguments.next().ok_or("missing secret key path")?);
    let artifact = PathBuf::from(arguments.next().ok_or("missing artifact path")?);
    if arguments.next().is_some() {
        return Err("unexpected extra arguments".into());
    }
    let password = env::var("CODINAL_UPDATE_SIGNING_PASSWORD")
        .ok()
        .map(Zeroizing::new);
    let encoded = sign_artifact(
        &secret_key,
        &artifact,
        password.as_ref().map(|password| password.as_str()),
    )?;
    io::stdout().write_all(encoded.as_bytes())?;
    io::stdout().write_all(b"\n")?;
    Ok(())
}

fn sign_artifact(
    secret_key_path: &std::path::Path,
    artifact_path: &std::path::Path,
    password: Option<&str>,
) -> Result<String, Box<dyn std::error::Error>> {
    let secret_key = load_secret_key(secret_key_path, password)?;
    let signature = sign(None, &secret_key, File::open(artifact_path)?, None, None)?;
    Ok(base64::engine::general_purpose::STANDARD.encode(signature.to_string()))
}

fn load_secret_key(
    path: &std::path::Path,
    password: Option<&str>,
) -> Result<SecretKey, Box<dyn std::error::Error>> {
    let stored = Zeroizing::new(fs::read_to_string(path)?);
    let decoded = if stored.trim_start().starts_with("untrusted comment:") {
        Zeroizing::new(stored.trim().to_owned())
    } else {
        let bytes = base64::engine::general_purpose::STANDARD.decode(stored.trim())?;
        Zeroizing::new(String::from_utf8(bytes)?)
    };
    let boxed = SecretKeyBox::from_string(&decoded)?;
    Ok(match password {
        Some(password) => SecretKey::from_box(boxed, Some(password.to_owned()))?,
        None => SecretKey::from_unencrypted_box(boxed)?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use minisign::KeyPair;
    use minisign_verify::{PublicKey, Signature};

    #[test]
    fn tauri_compatible_base64_key_and_signature_round_trip() {
        let temp = tempfile::tempdir().unwrap();
        let key_path = temp.path().join("update.key");
        let artifact_path = temp.path().join("artifact.tar.gz");
        let key_pair = KeyPair::generate_unencrypted_keypair().unwrap();
        let secret_box = key_pair.sk.to_box(None).unwrap().to_string();
        fs::write(
            &key_path,
            base64::engine::general_purpose::STANDARD.encode(secret_box),
        )
        .unwrap();
        fs::write(&artifact_path, b"signed update payload").unwrap();

        let encoded_signature = sign_artifact(&key_path, &artifact_path, None).unwrap();
        let signature_text = String::from_utf8(
            base64::engine::general_purpose::STANDARD
                .decode(encoded_signature)
                .unwrap(),
        )
        .unwrap();
        let public_key = PublicKey::decode(&key_pair.pk.to_box().unwrap().to_string()).unwrap();
        let signature = Signature::decode(&signature_text).unwrap();
        public_key
            .verify(b"signed update payload", &signature, true)
            .unwrap();
    }
}
