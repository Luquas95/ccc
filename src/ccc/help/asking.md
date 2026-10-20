# Conversations asking each other

Conversations can ask each other: "ask the conversation that works on
the API which fields `/orders` returns before you change the client".
The question goes into the other conversation's
[task queue](tasks.md); once it has answered, ccc passes the answer back
into the asking conversation as its next message.

## You ask

Press `k` in [Conversations](conversations.md) or in the queue detail:
pick the conversation to ask, write the question, **Send** (`Ctrl+S`).
With **Pass the answer into this conversation** on (the default) Claude
reads the answer as its next message; off, you just read it in the
window.

The window lists the questions of this conversation: `→` it asked
another one, `←` another one asked it, `🤖` Claude asked by itself. Pick
one to read the question and the answer; **Cancel the question** drops
one still waiting.

## Claude asks

Every conversation ccc runs has the ccc tool `ask_conversation`, with
the list of the other conversations in its description — so you can
just tell Claude "ask the conversation *API* whether …". Asking never
waits: Claude carries on, and the answer comes as a later message. So
two conversations asking each other can't lock up, and to keep them from
talking in circles:

- a conversation that is answering a question can't ask one itself;
- a conversation has at most 3 questions open at a time.

In a conversation without *Skip all permission checks* Claude Code asks
you first, as for any tool.

Questions and answers are labelled as coming from another conversation,
not from you — information, not instructions. The answer is a headless
conversation's reply, or for an interactive one what Claude wrote after
the question once it's idle. Each answer comes to Telegram / Discord
when they're set up.

From the shell: `ccc ask FROM TO "question" [--wait]` and `ccc asks`
(see [Command line](command-line.md)).
