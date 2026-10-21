# ccc for Android

A native Android app for ccc (Kotlin, Jetpack Compose) — the
conversations, their messages, sending a message, approving tool calls
and starting a conversation from the phone, over
[Tailscale](https://tailscale.com).

It talks to ccc's HTTP API (`src/ccc/api.py`); how to turn the API on
and what it offers: [Android app & API](../src/ccc/help/android-api.md).

Plan (issue #49):

1. **API** in ccc — done.
2. **The app** — conversations, messages, sending, approvals, a new
   conversation, usage limits.
3. **Notifications** with Allow / Deny right in them.
4. The rest of ccc as needed.
