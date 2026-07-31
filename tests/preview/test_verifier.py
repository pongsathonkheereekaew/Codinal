import pytest

from runtime.preview.verifier import PreviewVerificationError, verify_origin


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://localhost:3000",
        "http://192.168.1.2:3000",
        "http://localhost",
        "ftp://localhost:3000",
        "http://localhost:0",
    ],
)
def test_verify_origin_rejects_non_loopback_or_unbound_urls(url):
    with pytest.raises(PreviewVerificationError):
        verify_origin(url)


def test_verify_origin_canonicalizes_loopback_url():
    assert verify_origin("http://127.0.0.1:3000/app") == "http://127.0.0.1:3000/app"
