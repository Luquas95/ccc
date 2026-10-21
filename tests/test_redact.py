import pytest

from ccc.notify import DISCORD_WEBHOOK_KEY, TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY, Notifier
from ccc.redact import MASK, redact
from ccc.storage import Storage


@pytest.mark.parametrize("secret, kept", [
    ("sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz012345", "sk-ant-"),
    ("sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz01", "sk-proj-"),
    ("ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "ghp_"),
    ("github_pat_11ABCDEFG0123456789_abcdefghij", "github_pat_"),
    ("glpat-AbCdEfGhIjKlMnOpQrSt", "glpat-"),
    ("xoxb-1234567890-abcdefghij", "xoxb-"),
    ("AKIAIOSFODNN7EXAMPLE", "AKIA"),
    ("AIzaSyA-1234567890abcdefghijklmnopqrstu", "AIza"),
    ("sk_live_AbCdEfGhIjKlMnOpQr", "sk_live_"),
    ("123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsawQ", "123456789:"),
    ("https://discord.com/api/webhooks/123456/AbC-dEf_GhI", "https://discord.com/api/webhooks/123456/"),
    ("Bearer abcdefghijklmnop.qrstuv", "Bearer "),
])
def test_shaped_secrets_are_masked_keeping_their_prefix(secret, kept):
    out = redact(f"look: {secret} done")
    assert out == f"look: {kept}{MASK} done"


def test_jwt_and_private_key_block():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    assert redact(f"token {jwt}") == f"token {MASK}"
    pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\nAAAA\n-----END OPENSSH PRIVATE KEY-----"
    assert redact(f"key:\n{pem}\nafter") == f"key:\n{MASK}\nafter"


def test_password_in_url():
    assert redact("postgres://app:hunter2secret@db:5432/x") == f"postgres://app:{MASK}@db:5432/x"


@pytest.mark.parametrize("text, expected", [
    ("DB_PASSWORD=hunter2secret", f"DB_PASSWORD={MASK}"),
    ('"client_secret": "abcdef123456"', f'"client_secret": "{MASK}"'),
    ("api_key: 9f8e7d6c5b4a", f"api_key: {MASK}"),
    ("export GITLAB_TOKEN='zzzzzzzzzz'", f"export GITLAB_TOKEN='{MASK}'"),
])
def test_named_secrets(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize("text", [
    "API_KEY=${API_KEY}",
    "password: <your password>",
    "token=true",
    "Fixed the login redirect; the password field now validates.",
    "author=Luquas95",
    "max_tokens=4096",
    "passed=123456",
])
def test_harmless_text_is_left_alone(text):
    assert redact(text) == text


def test_named_after_shaped_does_not_double_mask():
    assert redact("ANTHROPIC_API_KEY=sk-ant-api03-AbCdEfGhIjKlMnOpQrSt") == f"ANTHROPIC_API_KEY=sk-ant-{MASK}"


def test_known_values_are_masked_whatever_their_shape():
    assert redact("my own: weird*value!", known=["weird*value!", None, ""]) == f"my own: {MASK}"


def test_empty_text():
    assert redact("") == ""


def _storage(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(TELEGRAM_TOKEN_KEY, "999:TOKENVALUE")
    storage.set_setting(TELEGRAM_CHAT_KEY, "42")
    storage.set_setting(DISCORD_WEBHOOK_KEY, "https://discord.com/api/webhooks/1/HOOKSECRET")
    return storage


def test_notifier_masks_what_it_sends(tmp_path):
    sent_tg, sent_dc = [], []
    notifier = Notifier(_storage(tmp_path), sender=lambda t, c, text: sent_tg.append(text),
                        discord_sender=lambda url, text: sent_dc.append(text))
    assert notifier.send_now("done: OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz and 999:TOKENVALUE")
    for text in sent_tg + sent_dc:
        assert "abcdefghijklmnopqrstuvwxyz" not in text and "TOKENVALUE" not in text
        assert text.startswith("done: OPENAI_API_KEY=sk-[redacted]")
