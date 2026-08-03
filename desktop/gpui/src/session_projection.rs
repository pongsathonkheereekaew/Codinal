//! Pure session-event parsing and replay-order validation.
//!
//! The projection boundary accepts only bounded, typed event metadata.  GPUI
//! rendering and runtime effects consume its result; this module owns no
//! window, network, filesystem, or runtime authority.

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct ParsedSessionEvent {
    pub(crate) event_type: String,
    pub(crate) turn_id: Option<String>,
    pub(crate) sequence: Option<u64>,
    pub(crate) global_sequence: Option<u64>,
    pub(crate) text: String,
    pub(crate) name: String,
    pub(crate) status: String,
    pub(crate) error: String,
}

pub(crate) fn parse_session_event(raw: &[u8]) -> Option<ParsedSessionEvent> {
    let event: serde_json::Value = serde_json::from_slice(raw).ok()?;
    let object = event.as_object()?;
    let event_type = object.get("type")?.as_str()?.to_owned();
    Some(ParsedSessionEvent {
        event_type,
        turn_id: object
            .get("turn_id")
            .and_then(serde_json::Value::as_str)
            .map(str::to_owned),
        sequence: object.get("sequence").and_then(serde_json::Value::as_u64),
        global_sequence: object
            .get("global_sequence")
            .and_then(serde_json::Value::as_u64),
        text: object
            .get("text")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_owned(),
        name: object
            .get("name")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_owned(),
        status: object
            .get("status")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_owned(),
        error: object
            .get("error")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_owned(),
    })
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum SessionEventOrder {
    Apply,
    Duplicate,
    Invalid,
}

pub(crate) fn session_event_order(
    last_global_sequence: &mut Option<u64>,
    event: &ParsedSessionEvent,
) -> SessionEventOrder {
    if event.event_type == "reload_required" {
        *last_global_sequence = None;
        return SessionEventOrder::Apply;
    }
    if event.event_type == "stream_error" {
        return SessionEventOrder::Apply;
    }
    if event.turn_id.as_deref().is_none_or(str::is_empty) || event.sequence.is_none() {
        return SessionEventOrder::Invalid;
    }
    let Some(global_sequence) = event.global_sequence else {
        return SessionEventOrder::Invalid;
    };
    if last_global_sequence.is_some_and(|last| global_sequence <= last) {
        return SessionEventOrder::Duplicate;
    }
    *last_global_sequence = Some(global_sequence);
    SessionEventOrder::Apply
}

#[cfg(test)]
mod tests {
    use super::{parse_session_event, session_event_order, SessionEventOrder};

    #[test]
    fn parser_rejects_malformed_or_missing_event_type() {
        assert!(parse_session_event(b"not-json").is_none());
        assert!(parse_session_event(br#"{"sequence":1}"#).is_none());
    }

    #[test]
    fn ordering_rejects_replay_and_resets_on_reload() {
        let event = |global_sequence| {
            parse_session_event(
                format!(
                    r#"{{"type":"turn_started","turn_id":"turn-1","sequence":1,"global_sequence":{global_sequence}}}"#
                )
                .as_bytes(),
            )
            .expect("event")
        };
        let mut last = None;
        assert_eq!(
            session_event_order(&mut last, &event(10)),
            SessionEventOrder::Apply
        );
        assert_eq!(
            session_event_order(&mut last, &event(10)),
            SessionEventOrder::Duplicate
        );
        assert_eq!(
            session_event_order(&mut last, &event(9)),
            SessionEventOrder::Duplicate
        );
        assert_eq!(
            session_event_order(&mut last, &event(11)),
            SessionEventOrder::Apply
        );
        let reload = parse_session_event(br#"{"type":"reload_required"}"#).expect("reload");
        assert_eq!(
            session_event_order(&mut last, &reload),
            SessionEventOrder::Apply
        );
        assert_eq!(last, None);
    }

    #[test]
    fn ordering_rejects_events_without_turn_identity_or_sequence() {
        let event = parse_session_event(br#"{"type":"assistant_message","global_sequence":12}"#)
            .expect("event");
        assert_eq!(
            session_event_order(&mut Some(11), &event),
            SessionEventOrder::Invalid
        );
    }
}
