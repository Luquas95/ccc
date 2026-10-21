import subprocess
import time

from ccc import gitops
from ccc.file_mentions import FileIndex, mention_at, rank, walk_files


def test_mention_at_only_at_a_word_start():
    assert mention_at("look at @src/ap") == (8, "src/ap")
    assert mention_at("@") == (0, "")
    assert mention_at("mail me@example.com") is None
    assert mention_at("@done and more") is None  # a space after it: finished
    assert mention_at("no mention") is None


def test_rank_file_name_then_path_then_fuzzy_shorter_first():
    files = ["docs/login-guide.md", "src/app/login.py", "src/auth/views.py", "login/x.py", "lib/l_o_g_i_n.py"]
    assert rank(files, "login") == ["src/app/login.py", "docs/login-guide.md", "login/x.py", "lib/l_o_g_i_n.py"]
    assert rank(files, "LOGIN.PY")[0] == "src/app/login.py"
    assert rank(files, "zzz") == []
    assert rank(files, "", limit=2) == ["login/x.py", "lib/l_o_g_i_n.py"]  # shallow first


def test_rank_is_fast_on_a_big_repository():
    files = [f"pkg{i % 300}/module_{i}/file_{i}.py" for i in range(60_000)]
    started = time.perf_counter()
    assert rank(files, "fil59999")[0] == "pkg299/module_59999/file_59999.py"
    assert time.perf_counter() - started < 1.0  # in a thread anyway


def test_walk_skips_junk_and_stops_at_the_limit(tmp_path):
    for rel in ("a.py", "src/b.py", "node_modules/x/y.js", ".git/config", ".hidden/s.txt", "build/out.bin"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    assert walk_files(str(tmp_path)) == ["a.py", "src/b.py"]
    assert len(walk_files(str(tmp_path), limit=1)) == 1


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("secret.env\n")
    (tmp_path / "tracked.py").write_text("x")
    (tmp_path / "secret.env").write_text("x")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.py", ".gitignore"], check=True)
    (tmp_path / "new.py").write_text("x")
    return tmp_path


def test_git_lists_tracked_and_untracked_not_ignored(tmp_path):
    repo = _repo(tmp_path)
    assert sorted(gitops.listed_files(str(repo))) == [".gitignore", "new.py", "tracked.py"]
    assert gitops.listed_files(str(tmp_path / "missing")) is None


def test_index_uses_git_only_when_allowed_and_caches(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    calls = []
    real = gitops.listed_files
    monkeypatch.setattr(gitops, "listed_files", lambda cwd: calls.append(cwd) or real(cwd))
    index = FileIndex()
    assert "secret.env" in index.files(str(repo), use_git=False)  # walking: no git run
    assert calls == []
    assert "secret.env" not in index.files(str(repo), use_git=True)
    index.files(str(repo), use_git=True)
    assert len(calls) == 1  # cached
    assert FileIndex().files(str(tmp_path / "missing"), use_git=False) == []
