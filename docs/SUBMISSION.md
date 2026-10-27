# Parallel Match: submission (Inside the Game hackathon)

- Live demo: https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
- Demo video (under 2 minutes): https://youtu.be/Qt4DRwWWmOo
- Repo: https://github.com/evanyap7/Parallel-Match

## Category

**Best Multi-Agent System.** The Match Desk is a team of agents with distinct
roles: a Producer plans the run; a Narrator, Law Explainer and Historian draft
in parallel; a Fact-Checker, a Microsoft Agent Framework agent with tools,
verifies every number against the simulation, the season record (fetched
through MCP) and the Law; an Editor repairs what fails; a Recap Writer writes
the final answer. They coordinate through a shared case file, hand off to each
other, recover from failures (a rewrite that still fails restores the
deterministic text; a reviewer outage leaves the code checks in charge), and
every step is visible in an on-screen trace.

It also fits **Best Azure Cloud Native Integration**: four Azure Container Apps
(front end, simulator API, agents API, MCP server), a user-assigned managed
identity for image pulls and keyless Foundry access, and an MCP server the
agents call over streamable HTTP.

## Elevator pitch

Parallel Match lets a fan tap a contestable moment, a borderline penalty or a
tight offside, and ask "what if that call had gone the other way?". The screen
splits into the real match and an alternate match, re-simulated hundreds of
times with paired random numbers so the difference is the call, not luck.
A second opinion comes from the league's own season: comparable decisions and
what followed, and the app says plainly when the two disagree. A desk of
agents on Microsoft Agent Framework and Azure AI Foundry narrates both
timelines, explains the Law neutrally and cites precedent fetched through an
MCP server, while a Fact-Checker agent verifies every number with tools and an
Editor repairs what fails. Every number is computed in code, and it all works
in 18 languages. All data is synthetic. It runs on Azure Container Apps.

## Microsoft technologies used

- **Azure AI Foundry** (model `gpt-4.1-mini`) via **Microsoft Agent Framework**:
  the Match Desk (`agents/desk.py`: Producer, Narrator, Law Explainer, Historian,
  Fact-Checker with function tools, Editor, Recap Writer) and the Intervention
  Parser (`agents/`)
- **MCP**: `history_query` / `season_summary` server on Container Apps; the
  Historian fetches its facts through it (`mcp_history/`, `agents/history_client.py`)
- **Azure Container Apps**: four apps, user-assigned managed identity, Azure
  Container Registry (`deploy/`)

## Testing instructions (for judges)

No login needed. Works on desktop and phone.

1. Open https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
   and choose a language (English is fine).
2. Choose match **m052** (Westfield Rangers 2-1 Copperfield FC). On the
   timeline, pick the **penalty at 56'**.
3. Tap the question button ("What if…?"), or type your own, e.g. "what if
   that wasn't a penalty?". The match is replayed from that moment with the
   call reversed.
4. Read the verdict: how the result changes, as a shift in win share with its
   95% interval, and the alternate timeline's commentary.
5. Switch to the **Analyst** tab and scroll to the **Agent desk**: the agents'
   steps, the Fact-Checker's tool calls and the cross-checks. Open "Show the
   evidence" to see what each agent wrote. The m052 penalty is pre-cached;
   a moment seen for the first time takes about 15 to 25 seconds (the panel
   shows progress), then it is cached.
6. Also in the **Analyst** tab, the evidence: the decision and the Law it
   falls under, outcome shares, alternate final scores, the Historian's season
   precedent (fetched through the MCP server) and whether it agrees with the
   simulation, and the divergence log.
7. Try another match and moment. Featured moments answer in about a second;
   other moments are simulated live: up to about 15 seconds for an early
   moment, less for later ones.
8. Use the language menu in the top bar to switch the interface between 18
   languages (English, Spanish, Portuguese, French, German, Italian, Dutch,
   Polish, Russian, Turkish, Arabic, Hindi, Indonesian, Thai, Vietnamese,
   Chinese, Japanese, Korean). A language screen appears on first visit, and
   the agent text (commentary, Law, precedent, free-text "what if") follows
   the choice. Output is checked for numbers and neutral wording before it is
   shown; if a check fails the English text is served with a note.

Service health, for the curious: https://pm-agents.agreeableflower-13af161d.japaneast.azurecontainerapps.io/health shows the model provider
(Foundry) and the MCP connection. MCP endpoint (streamable HTTP):
https://pm-history-mcp.agreeableflower-13af161d.japaneast.azurecontainerapps.io/mcp.
