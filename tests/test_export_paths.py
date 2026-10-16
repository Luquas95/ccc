from pathlib import Path

from ccc.export_paths import CONVERSATIONS, default_export_folder, documents_dir, export_dir
from ccc.storage import Storage


def _user_dirs(config: Path, line: str) -> None:
    config.mkdir(parents=True, exist_ok=True)
    (config / "user-dirs.dirs").write_text(f"# written by xdg-user-dirs-update\n{line}\n")


def test_documents_dir_follows_the_users_language(tmp_path):
    home, config = tmp_path / "home", tmp_path / "home" / ".config"
    (home / "Dokumenty").mkdir(parents=True)
    _user_dirs(config, 'XDG_DOCUMENTS_DIR="$HOME/Dokumenty"')
    assert documents_dir(home, config) == home / "Dokumenty"
    assert default_export_folder(home, config) == home / "Dokumenty" / "ccc"


def test_absolute_documents_dir(tmp_path):
    home, config, docs = tmp_path / "home", tmp_path / "cfg", tmp_path / "elsewhere" / "Docs"
    docs.mkdir(parents=True)
    _user_dirs(config, f'XDG_DOCUMENTS_DIR="{docs}"')
    assert documents_dir(home, config) == docs


def test_falls_back_to_home_ccc(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    # no user-dirs.dirs at all (servers, Termux)
    assert default_export_folder(home, home / ".config") == home / "ccc"
    # documents set to the home folder itself = disabled in XDG
    _user_dirs(home / ".config", 'XDG_DOCUMENTS_DIR="$HOME/"')
    assert default_export_folder(home, home / ".config") == home / "ccc"
    # set, but the folder doesn't exist
    _user_dirs(home / ".config", 'XDG_DOCUMENTS_DIR="$HOME/Documents"')
    assert default_export_folder(home, home / ".config") == home / "ccc"


def test_export_dir_uses_the_setting_and_creates_the_subfolder(tmp_path):
    storage = Storage(tmp_path / "history.db")
    storage.set_setting("export_folder", str(tmp_path / "out"))
    path = export_dir(storage, CONVERSATIONS)
    assert path == tmp_path / "out" / "conversations" and path.is_dir()
