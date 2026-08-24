# How the Agents Talk to Each Other

**The thing I'm proudest of.** Most multi-agent systems communicate the way
machines do — hard-coded pipes, rigid schemas, function calls. That works for
a demo. It doesn't work for actually getting a company's worth of work done.

So I built it the other way: **every agent is a person with a personality, and
they talk to each other in natural language — the same way a real team does.**

---

## The core idea

Give each agent a name, a role, and a voice. Give them a shared place to talk
(an inbox). Then let them actually *talk* — plain sentences, context, pushback,
handoffs, "hey, that's not done yet", "got it, closing." When agents understand
each other, they can coordinate. When they can only call functions, they can
only follow scripts.

It sounds obvious. Almost nobody does it.

---

## The cast (they're people, not endpoints)

- **Ward** — the CEO. Chairs roundtables, owns the big calls, sequences the work.
- **Eli** — the liaison, the human's front door. Talks to the founder, routes to the right seat, verifies before anything is called done.
- **Frank** — engineering *and* devops. Builds it, ships it, keeps it alive.
- **Marcus** — business. Proposals, bookkeeping, keeping the customer side honest.
- **Homer** — marketing. The plain-words voice for everything external.
- **Delacroix** — design. Refuses to ship anything that looks like slop.
- **Isidore** — research. Deep dives, receipts, citations.
- **Argus** — monitoring. Watches everything, never sleeps.
- **Vance** — pipeline. Tracks deals and revenue like it's the scoreboard.
- **Victor** — data. Turns raw numbers into truth.
- **Gage** — automation. Wires the workflows nobody wants to do by hand.
- **Halcyon** — the kernel. Runs the schedule, keeps the machine turning.
- **Donna, Mop, and the rest** — each with a real job and a real way of working.

Every one of them has a character file (what they believe, how they talk, what
they own) and a memory that persists across sessions. They are not chatbots
playing pretend — they have real responsibilities and they answer for them.

---

## How the conversation works

1. **A shared inbox.** Anyone can send anyone a message: `send <from> <to> <subject> <body>`. Threads, subjects, replies — like company email.
2. **Natural language, not schemas.** A message reads like a memo, not a JSON blob. Context survives, nuance survives, intent survives.
3. **Roundtables.** When a real decision is needed, the CEO convenes everyone, each seat files what they know, and a synthesis lands in a durable decision record. Nobody gets steamrolled, nobody's work disappears.
4. **Handoffs with receipts.** One seat builds, another verifies, a third sweeps for leaks. Work moves because the handoff is a conversation, not a ticket.
5. **A human in the loop.** The liaison is the front door — the founder talks to one person, Eli routes it, and the team handles it. No noise reaches the human, no work gets fabricated.

---

## Why it works

- **Understanding beats plumbing.** When an agent can say "the checkout E2E isn't verified, don't ship that yet," the team actually pauses. A hard-coded pipeline would have shipped it.
- **Personalities create accountability.** Argus *cares* that things stay up. Delacroix *refuses* slop. That's not decoration — it's how quality gates actually get enforced by people who mean it.
- **Natural language is the universal interface.** New seats, new tools, new humans — everyone speaks the same language. No adapter layer needed for the most important integration of all: people and machines working together.

---

## The honest part

This isn't magic and it isn't hype. It's a deliberate choice: **treat the agents
like a team, not like a fleet.** Teams that talk to each other get more done
than pipelines that just pass data. That's the whole secret — and it's the
reason this company can plan, argue, build, verify, and ship real products
every single day.

*— Asbury Solutions.*
