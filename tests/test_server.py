from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from unittest.mock import Mock

import pytest

import server


@pytest.fixture
def static_server(tmp_path, monkeypatch):
    (tmp_path / "landing.html").write_text("public landing", encoding="utf-8")
    (tmp_path / ".env").write_text("PRIVATE_DUMMY_KEY", encoding="utf-8")
    monkeypatch.setattr(server.Handler, "log_message", lambda *args: None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(server.Handler, directory=str(tmp_path)))
    worker = Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    yield httpd.server_port
    httpd.shutdown()
    httpd.server_close()
    worker.join(timeout=2)


def get(port, path, method="GET"):
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("path", ["/.env", "/.git/config", "/audit/audit.jsonl", "/server.py", "/../.env", "/%2eenv"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_private_files_are_not_served(static_server, path, method):
    status, _, body = get(static_server, path, method)
    assert status == 404
    assert b"PRIVATE_DUMMY_KEY" not in body


@pytest.mark.parametrize("path", ["/", "/index.html", "/landing.html?source=test"])
def test_public_landing_routes_still_work(static_server, path):
    status, _, body = get(static_server, path)
    assert status == 200
    assert body == b"public landing"


def test_app_redirect_still_works(static_server):
    status, headers, _ = get(static_server, "/app")
    assert status == 302
    assert headers["Location"] == f"http://localhost:{server.STREAMLIT_PORT}"


def test_streamlit_uses_current_interpreter_and_project_directory(monkeypatch):
    popen = Mock()
    monkeypatch.setattr(server.subprocess, "Popen", popen)
    assert server.start_streamlit() is popen.return_value
    assert popen.call_args.args[0][:3] == [server.sys.executable, "-m", "streamlit"]
    assert popen.call_args.kwargs["cwd"] == server.ROOT
    assert "--server.headless" in popen.call_args.args[0]
    assert "--server.address" in popen.call_args.args[0]
