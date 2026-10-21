from ccc.diff_comments import ADDED, CONTEXT, HEADER, HUNK, META, REMOVED, Comment, parse, prompt

SHOW = """commit abcdef1234567
Author: t <t@t>

    Fix login

 src/app.py | 3 ++-
 2 files changed

diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,3 +10,4 @@ def login():
 keep = 1
-old = 2
+new = 2
+extra = 3
\\ No newline at end of file
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""


def test_parse_knows_files_and_line_numbers():
    lines = parse(SHOW)
    by_text = {line.text: line for line in lines}
    assert by_text["commit abcdef1234567"].kind == HEADER
    assert by_text[" src/app.py | 3 ++-"].kind == HEADER  # the stat isn't a hunk
    assert by_text["--- a/src/app.py"].kind == META
    hunk = by_text["@@ -10,3 +10,4 @@ def login():"]
    assert (hunk.kind, hunk.path, hunk.new_line) == (HUNK, "src/app.py", 10)
    assert (by_text[" keep = 1"].kind, by_text[" keep = 1"].new_line) == (CONTEXT, 10)
    assert (by_text["-old = 2"].kind, by_text["-old = 2"].old_line) == (REMOVED, 11)
    assert (by_text["+new = 2"].kind, by_text["+new = 2"].new_line) == (ADDED, 11)
    assert by_text["+extra = 3"].new_line == 12
    gone = by_text["-bye"]
    assert (gone.kind, gone.path, gone.old_line) == (REMOVED, "gone.txt", 1)
    assert not by_text["diff --git a/gone.txt b/gone.txt"].commentable
    assert not by_text["    Fix login"].commentable


def test_prompt_lists_each_comment_with_place_and_quote():
    lines = {line.text: line for line in parse(SHOW)}
    text = prompt("abcdef1234567", "Fix login", [
        Comment(lines["+new = 2"], "  rename it  "),
        Comment(lines["-bye"], "why delete?"),
    ])
    assert "abcdef1" in text and "Fix login" in text
    assert "1. src/app.py:11\n   > +new = 2\n   rename it" in text
    assert "2. gone.txt, removed line 1\n   > -bye\n   why delete?" in text
