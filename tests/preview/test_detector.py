"""Dev-server URL detector tests."""

from runtime.preview.detector import detect_devserver_urls


def test_detects_localhost_urls():
    output = (
        "VITE v5.0.0 ready in 312 ms\n"
        "➜  Local:   http://localhost:5173/\n"
        "➜  Network: http://192.168.1.5:5173/\n"
    )

    urls = detect_devserver_urls(output)

    assert len(urls) == 1
    assert urls[0]["url"] == "http://localhost:5173/"
    assert urls[0]["port"] == 5173


def test_detects_127_loopback_urls():
    output = "Server running at http://127.0.0.1:3000"

    urls = detect_devserver_urls(output)

    assert urls[0]["url"] == "http://127.0.0.1:3000"
    assert urls[0]["port"] == 3000


def test_ignores_non_localhost_urls():
    output = "Deployed at https://example.com:443/path"

    urls = detect_devserver_urls(output)

    assert urls == []


def test_deduplicates_repeated_urls():
    output = "http://localhost:8080 http://localhost:8080 http://localhost:8080"

    urls = detect_devserver_urls(output)

    assert len(urls) == 1


def test_bounds_to_max_urls():
    output = " ".join(
        f"http://localhost:{port}" for port in range(9000, 9020)
    )

    urls = detect_devserver_urls(output)

    assert len(urls) <= 8


def test_handles_empty_and_non_string():
    assert detect_devserver_urls("") == []
    assert detect_devserver_urls(None) == []  # type: ignore[arg-type]


def test_strips_trailing_punctuation():
    output = "ready on http://localhost:4000."

    urls = detect_devserver_urls(output)

    assert urls[0]["url"] == "http://localhost:4000"
