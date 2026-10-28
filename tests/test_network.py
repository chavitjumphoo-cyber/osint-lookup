import io
import socket
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from osint_agent import advanced_tools, network, tools


def image_response(data):
    response = Mock(status_code=200, is_redirect=False)
    response.headers = {"Content-Type": "image/png"}
    response.iter_content.return_value = [data]
    return response


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *args: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
    ])
    monkeypatch.setattr(network.RATE_LIMITER, "wait", lambda host: None)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/private.png", "http://169.254.169.254/image",
    "http://192.168.1.1/image", "http://[::1]/image",
])
def test_avatar_private_url_is_rejected_before_request(url, monkeypatch):
    get = Mock(side_effect=AssertionError("Private URL reached HTTP client"))
    monkeypatch.setattr(network.requests, "get", get)
    assert "error" in advanced_tools.compare_avatars(url, url)
    get.assert_not_called()


def test_agent_avatar_tool_rejects_local_file_paths():
    output = tools.execute_tool("compare_avatars", {
        "avatar_url_1": "/etc/passwd", "avatar_url_2": "file:///tmp/photo.png",
    })
    assert "ข้อผิดพลาด" in output["output"]


def test_public_avatar_still_matches_image_bytes(public_dns, monkeypatch):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    data = buffer.getvalue()
    response = image_response(data)
    get = Mock(return_value=response)
    monkeypatch.setattr(network.requests, "get", get)
    result = advanced_tools.compare_avatars("https://example.com/avatar.png", data)
    assert result["matched"] is True
    assert result["similarity_percentage"] == 100
    assert get.call_args.kwargs["allow_redirects"] is False
    response.close.assert_called_once()


def test_private_redirect_is_blocked(monkeypatch):
    def resolve(host, *args):
        ip = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(network.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(network.RATE_LIMITER, "wait", lambda host: None)
    response = Mock(status_code=302, is_redirect=True)
    response.headers = {"Location": "http://127.0.0.1/private.png"}
    get = Mock(return_value=response)
    monkeypatch.setattr(network.requests, "get", get)
    with pytest.raises(network.UnsafeURLError):
        network.download_image("https://example.com/redirect")
    get.assert_called_once()
    response.close.assert_called_once()


def test_oversized_image_is_rejected_and_closed(monkeypatch):
    response = image_response(b"12345")
    monkeypatch.setattr(network, "safe_get", lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match="ขนาด"):
        network.download_image("https://example.com/avatar.png", max_bytes=4)
    response.close.assert_called_once()


def test_failed_image_download_is_closed(monkeypatch):
    response = image_response(b"")
    response.raise_for_status.side_effect = requests.HTTPError("404")
    monkeypatch.setattr(network, "safe_get", lambda *args, **kwargs: response)
    with pytest.raises(requests.HTTPError):
        network.download_image("https://example.com/avatar.png")
    response.close.assert_called_once()


@pytest.mark.parametrize("url", ["https://user:pass@example.com/image", "http://example.com:bad/image", "http://[bad/image"])
def test_malformed_or_credentialed_urls_are_rejected(url):
    with pytest.raises(network.UnsafeURLError):
        network._check_url(url)
