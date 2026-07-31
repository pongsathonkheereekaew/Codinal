use std::io;

use objc2::{MainThreadMarker, MainThreadOnly};
use objc2_app_kit::{
    NSAlert, NSAlertFirstButtonReturn, NSAlertSecondButtonReturn, NSSecureTextField, NSTextField,
};
use objc2_foundation::{NSPoint, NSRect, NSSize, NSString};
use zeroize::Zeroizing;

pub fn prompt_api_key(provider: &str) -> io::Result<Option<Zeroizing<String>>> {
    let mtm = MainThreadMarker::new().ok_or_else(|| {
        io::Error::other("secure credential prompt must run on the macOS main thread")
    })?;
    let alert = NSAlert::new(mtm);
    alert.setMessageText(&NSString::from_str("Set provider credential"));
    alert.setInformativeText(&NSString::from_str(&format!(
        "Enter the API key for {provider}. The value is stored in Keychain and is never displayed."
    )));
    alert.addButtonWithTitle(&NSString::from_str("Save"));
    alert.addButtonWithTitle(&NSString::from_str("Cancel"));

    let field = NSSecureTextField::initWithFrame(
        NSSecureTextField::alloc(mtm),
        NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(360.0, 24.0)),
    );
    alert.setAccessoryView(Some(&field));
    let accepted = alert.runModal() == NSAlertFirstButtonReturn;
    let value = accepted.then(|| Zeroizing::new(field.stringValue().to_string()));
    field.setStringValue(&NSString::from_str(""));
    Ok(value)
}

pub fn prompt_text(title: &str, detail: &str, initial_value: &str) -> io::Result<Option<String>> {
    let mtm = MainThreadMarker::new()
        .ok_or_else(|| io::Error::other("native text prompt must run on the macOS main thread"))?;
    let alert = NSAlert::new(mtm);
    alert.setMessageText(&NSString::from_str(title));
    alert.setInformativeText(&NSString::from_str(detail));
    alert.addButtonWithTitle(&NSString::from_str("Continue"));
    alert.addButtonWithTitle(&NSString::from_str("Cancel"));

    let field = NSTextField::initWithFrame(
        NSTextField::alloc(mtm),
        NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(360.0, 24.0)),
    );
    field.setStringValue(&NSString::from_str(initial_value));
    alert.setAccessoryView(Some(&field));
    let accepted = alert.runModal() == NSAlertFirstButtonReturn;
    let value = accepted.then(|| field.stringValue().to_string());
    field.setStringValue(&NSString::from_str(""));
    Ok(value)
}

pub fn prompt_boolean(title: &str, detail: &str) -> io::Result<Option<bool>> {
    let mtm = MainThreadMarker::new().ok_or_else(|| {
        io::Error::other("native boolean prompt must run on the macOS main thread")
    })?;
    let alert = NSAlert::new(mtm);
    alert.setMessageText(&NSString::from_str(title));
    alert.setInformativeText(&NSString::from_str(detail));
    alert.addButtonWithTitle(&NSString::from_str("Eligible"));
    alert.addButtonWithTitle(&NSString::from_str("Not eligible"));
    alert.addButtonWithTitle(&NSString::from_str("Cancel"));
    Ok(match alert.runModal() {
        response if response == NSAlertFirstButtonReturn => Some(true),
        response if response == NSAlertSecondButtonReturn => Some(false),
        _ => None,
    })
}
