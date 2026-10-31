import pytest

from ccc import api, api_scope
from ccc.storage import Storage


@pytest.fixture
def closed(tmp_path):
    """A fresh storage with the scope as shipped: no roots, skipping permissions not allowed."""
    return Storage(str(tmp_path / "scope.db"))


def _create(storage, path, **body):
    return api.Api(storage).route("POST", "/api/v1/conversations", {}, {"path": str(path), "interactive": False, **body})


def test_without_roots_only_folders_ccc_knows_are_allowed(closed, tmp_path):
    known = tmp_path / "shop"
    known.mkdir()
    closed.create_queue("shop", str(known), "s1")
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert api_scope.check_folder(closed, str(known)) == str(known)
    assert api_scope.check_folder(closed, str(known / "sub")) == str(known / "sub")  # inside a known one
    with pytest.raises(api.ApiError) as error:
        api_scope.check_folder(closed, str(other))
    assert error.value.status == 403


def test_a_root_allows_everything_inside_it_but_not_its_siblings_or_a_lookalike(closed, tmp_path):
    root = tmp_path / "dev"
    (root / "a").mkdir(parents=True)
    (tmp_path / "dev-evil").mkdir()
    api_scope.add_root(closed, str(root))
    assert api_scope.check_folder(closed, str(root / "a"))
    for outside in (tmp_path, tmp_path / "dev-evil", "/", "~"):
        with pytest.raises(api.ApiError):
            api_scope.check_folder(closed, str(outside))


def test_a_symlink_out_of_the_root_does_not_get_out(closed, tmp_path):
    root = tmp_path / "dev"
    root.mkdir()
    (tmp_path / "secret").mkdir()
    (root / "link").symlink_to(tmp_path / "secret")
    api_scope.add_root(closed, str(root))
    with pytest.raises(api.ApiError):
        api_scope.check_folder(closed, str(root / "link"))
    with pytest.raises(api.ApiError):
        api_scope.check_folder(closed, str(root / ".." / "secret"))


def test_roots_are_added_removed_and_must_exist(closed, tmp_path):
    folder = tmp_path / "dev"
    folder.mkdir()
    api_scope.add_root(closed, str(folder))
    api_scope.add_root(closed, str(folder))
    assert api_scope.roots(closed) == [folder]
    with pytest.raises(ValueError):
        api_scope.add_root(closed, str(tmp_path / "nope"))
    assert api_scope.remove_root(closed, str(folder)) and not api_scope.remove_root(closed, str(folder))
    assert api_scope.roots(closed) == []


def test_creating_outside_the_roots_is_refused_and_inside_works(closed, tmp_path):
    inside, outside = tmp_path / "dev" / "x", tmp_path / "y"
    inside.mkdir(parents=True)
    outside.mkdir()
    api_scope.add_root(closed, str(tmp_path / "dev"))
    api_scope.set_skip_allowed(closed, True)
    with pytest.raises(api.ApiError) as error:
        _create(closed, outside)
    assert error.value.status == 403
    assert _create(closed, inside)[0] == 201


def test_sessions_and_mcp_servers_of_a_foreign_folder_are_refused(closed, tmp_path):
    for path in ("/api/v1/sessions", "/api/v1/mcp-servers"):
        with pytest.raises(api.ApiError) as error:
            api.Api(closed).route("GET", path, {"path": str(tmp_path)}, {})
        assert error.value.status == 403


def test_skipping_permissions_is_refused_until_allowed(closed, tmp_path):
    folder = tmp_path / "dev"
    folder.mkdir()
    api_scope.add_root(closed, str(folder))
    with pytest.raises(api.ApiError) as error:
        _create(closed, folder, options=["perm_skip"])
    assert error.value.status == 403
    api_scope.set_skip_allowed(closed, True)
    status, result = _create(closed, folder, options=["perm_skip"])
    assert status == 201 and "--dangerously-skip-permissions" in closed.get_queue(result["id"]).launch_flags


def test_the_phones_defaults_ask_for_everything_unless_skipping_is_allowed(closed, tmp_path):
    folder = tmp_path / "dev"
    folder.mkdir()
    api_scope.add_root(closed, str(folder))
    assert "perm_skip" not in api.Api(closed).route("GET", "/api/v1/launch-options", {}, {})[1]["default"]
    status, result = _create(closed, folder)  # no options: the defaults
    assert status == 201
    assert "--dangerously-skip-permissions" not in closed.get_queue(result["id"]).launch_flags
    api_scope.set_skip_allowed(closed, True)
    assert "perm_skip" in api.Api(closed).route("GET", "/api/v1/launch-options", {}, {})[1]["default"]


def test_cli_roots_and_skip_permissions(closed, tmp_path, capsys):
    from argparse import Namespace
    from ccc import api_cli

    folder = tmp_path / "dev"
    folder.mkdir()
    assert api_cli.run(closed, "", Namespace(api_command="roots", add=str(folder), remove=None)) == 0
    assert api_scope.roots(closed) == [folder]
    assert api_cli.run(closed, "", Namespace(api_command="roots", add=str(tmp_path / "nope"), remove=None)) == 1
    assert api_cli.run(closed, "", Namespace(api_command="roots", add=None, remove=str(folder))) == 0
    assert api_cli.run(closed, "", Namespace(api_command="skip-permissions", state="on")) == 0
    assert api_scope.skip_allowed(closed)
    api_cli.run(closed, "", Namespace(api_command="skip-permissions", state=None))
    assert api_scope.skip_allowed(closed)
