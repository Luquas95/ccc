from ccc.list_filter import fold, parse
from ccc.models import Queue, QueueStatus


def _q(name="shop-api", path="/home/me/shop", status=QueueStatus.IDLE):
    return Queue(id=1, name=name, project_path=path, session_id="s", status=status)


def test_fold_drops_case_and_diacritics():
    assert fold("Příliš ŽLUŤOUČKÝ") == "prilis zlutoucky"


def test_empty_filter_matches_everything():
    f = parse("   ")
    assert not f.active
    assert f.matches(_q())


def test_words_match_name_or_folder_all_of_them():
    assert parse("API").matches(_q())
    assert parse("shop me").matches(_q(name="x"))  # folder
    assert not parse("api docs").matches(_q())
    assert parse("prilis").matches(_q(name="Příliš"))
    assert parse("Příliš").matches(_q(name="prilis"))


def test_state_markers_at_the_start():
    f = parse("? api")
    assert f.states == {"?"} and f.words == ("api",)
    assert f.matches(_q(), needs_approval=True)
    assert not f.matches(_q())
    assert parse("!").matches(_q(status=QueueStatus.RUNNING))
    assert not parse("!").matches(_q())
    assert parse("x").matches(_q(status=QueueStatus.BLOCKED_ERROR))
    assert parse("X").matches(_q(status=QueueStatus.BLOCKED_ERROR))
    assert parse("*").matches(_q(), unseen=True)
    assert not parse("*").matches(_q())


def test_several_markers_mean_any_state():
    f = parse("!? api")
    assert f.states == {"!", "?"}
    assert f.matches(_q(status=QueueStatus.RUNNING))
    assert f.matches(_q(), needs_approval=True)
    assert not f.matches(_q(status=QueueStatus.BLOCKED_ERROR))
    assert parse("! ?").states == {"!", "?"}


def test_marker_only_as_a_word_of_its_own_and_only_at_the_start():
    assert parse("xml").states == frozenset()
    assert parse("api ?").words == ("api", "?")
