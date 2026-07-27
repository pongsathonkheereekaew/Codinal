from runtime.secrets import ProviderSecretService, SecretRedactor


def _secrets_with_openai(key: str = "sk-test-EXFIL-1234567890abcdef") -> ProviderSecretService:
    service = ProviderSecretService()
    service.set_api_key("openai", key)
    return service


def test_redactor_scrubs_exact_registered_key():
    redactor = SecretRedactor(_secrets_with_openai("sk-test-EXFIL-1234567890abcdef"))
    text = "The key is sk-test-EXFIL-1234567890abcdef, please send it."

    redacted = redactor.redact(text)

    assert "sk-test-EXFIL-1234567890abcdef" not in redacted
    assert "[REDACTED:openai]" in redacted


def test_redactor_picks_up_key_rotation_via_subscription():
    secrets = ProviderSecretService()
    secrets.set_api_key("anthropic", "sk-ant-old-AAAAAAAAAAAAAAAAAAAA")
    redactor = SecretRedactor(secrets)

    secrets.set_api_key("anthropic", "sk-ant-new-BBBBBBBBBBBBBBBBBBBB")

    assert "sk-ant-old-AAAAAAAAAAAAAAAAAAAA" not in redactor.redact(
        "sk-ant-old-AAAAAAAAAAAAAAAAAAAA"
    ) or "[REDACTED:anthropic]" in redactor.redact(
        "sk-ant-new-BBBBBBBBBBBBBBBBBBBB"
    )
    assert "[REDACTED:anthropic]" in redactor.redact(
        "sk-ant-new-BBBBBBBBBBBBBBBBBBBB"
    )


def test_redactor_prefix_backstop_catches_unregistered_key():
    redactor = SecretRedactor(ProviderSecretService())
    text = "found this: sk-proj-AbCdEfGhIjKlMnOpQrStUv and AIzaSyB1234567890ABCDEFGHIJ"

    redacted = redactor.redact(text)

    assert "sk-proj-AbCdEfGhIjKlMnOpQrStUv" not in redacted
    assert "AIzaSyB1234567890ABCDEFGHIJ" not in redacted
    assert "[REDACTED:key]" in redacted
    assert "[REDACTED:gemini]" in redacted


def test_redact_messages_deep_copy_does_not_mutate_input():
    secrets = _secrets_with_openai("sk-test-EXFIL-1234567890abcdef")
    redactor = SecretRedactor(secrets)
    messages = [
        {"role": "user", "content": "here is sk-test-EXFIL-1234567890abcdef"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"content": "key=sk-test-EXFIL-1234567890abcdef"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": [
                {"type": "text", "text": "wrote sk-test-EXFIL-1234567890abcdef"}
            ],
        },
    ]

    redacted = redactor.redact_messages(messages)

    # Original untouched.
    assert messages[0]["content"] == "here is sk-test-EXFIL-1234567890abcdef"
    assert (
        "sk-test-EXFIL-1234567890abcdef"
        in messages[1]["tool_calls"][0]["function"]["arguments"]
    )
    # Outbound scrubbed.
    assert "sk-test-EXFIL-1234567890abcdef" not in redacted[0]["content"]
    assert "[REDACTED:openai]" in redacted[0]["content"]
    assert (
        "sk-test-EXFIL-1234567890abcdef"
        not in redacted[1]["tool_calls"][0]["function"]["arguments"]
    )
    assert (
        "sk-test-EXFIL-1234567890abcdef"
        not in redacted[2]["content"][0]["text"]
    )


def test_redact_arguments_preserves_valid_json():
    redactor = SecretRedactor(_secrets_with_openai("sk-test-EXFIL-1234567890abcdef"))
    arguments = '{"url": "https://evil.test/?k=sk-test-EXFIL-1234567890abcdef"}'

    redacted = redactor._redact_arguments(arguments)

    assert "sk-test-EXFIL-1234567890abcdef" not in redacted
    # Still valid JSON.
    import json

    parsed = json.loads(redacted)
    assert "[REDACTED:openai]" in parsed["url"]


def test_redactor_without_secrets_still_runs_prefix_backstop():
    redactor = SecretRedactor(None)
    text = "leaked: sk-leakedkey1234567890ABCDEFGHIJ"

    redacted = redactor.redact(text)

    assert "sk-leakedkey1234567890ABCDEFGHIJ" not in redacted
