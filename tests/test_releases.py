import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ccc import releases

RULES = json.loads((Path(__file__).parent / "fixtures" / "release-rules.json").read_text())


@pytest.mark.parametrize("text, expected", RULES["parse"])
def test_versions_parse_as_the_shared_rules_say(text, expected):
    assert releases.parse_version(text) == expected


@pytest.mark.parametrize("latest, installed, expected", RULES["newer"])
def test_versions_compare_as_the_shared_rules_say(latest, installed, expected):
    assert releases.is_newer(latest, installed) is expected


@pytest.mark.parametrize("case", RULES["releases"], ids=lambda c: c["name"])
def test_releases_are_picked_as_the_shared_rules_say(case):
    got = releases.parse_release(case["release"], case["asset"])
    expect = case["expect"]
    assert (got and {"version": got.version, "url": got.url, "notes": got.notes}) == expect


@pytest.fixture
def github():
    """A GitHub of its own: the release and the artifact it points at."""
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["auth"] = self.headers.get("Authorization")
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/repos/o/r/releases/latest":
                body = json.dumps({"tag_name": "0.2.0", "body": "News", "assets": [
                    {"name": "ccc.tar.gz", "browser_download_url": f"{base}/ccc.tar.gz"}]}).encode()
            elif self.path == "/ccc.tar.gz":
                body = b"SDIST"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", seen
    server.shutdown()


def test_asks_github_without_a_token_and_downloads_the_artifact(github, tmp_path):
    base, seen = github
    release = releases.latest("o/r", base)
    assert release.version == "0.2.0" and release.notes == "News"
    assert seen["auth"] is None
    target = tmp_path / "x" / "ccc.tar.gz"
    releases.download(release.url, target, check=lambda url: True)
    assert target.read_bytes() == b"SDIST" and not list(target.parent.glob("*.part"))


def test_no_release_yet_is_none_and_an_unreachable_github_is_an_error(github):
    base, _ = github
    assert releases.latest("o/missing", base) is None
    with pytest.raises(OSError):
        releases.latest("o/r", "http://127.0.0.1:1")


@pytest.mark.parametrize("url, ok", [
    ("https://github.com/o/r/releases/download/1.0.0/ccc.tar.gz", True),
    ("https://objects.githubusercontent.com/x", True),
    ("http://github.com/o/r/ccc.tar.gz", False),
    ("https://github.com.evil.example/ccc.tar.gz", False),
    ("file:///etc/passwd", False),
])
def test_only_github_over_https_is_trusted(url, ok, tmp_path):
    assert releases.trusted(url) is ok
    if not ok:
        with pytest.raises(OSError):
            releases.download(url, tmp_path / "x")
