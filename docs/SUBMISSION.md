# Parallel Match: submission (Inside the Game hackathon)

- Live demo: https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
- Demo video (under 2 minutes): https://youtu.be/Qt4DRwWWmOo
- Repo: https://github.com/evanyap7/Parallel-Match

## Category

**Best Azure Cloud Native Integration**: four Azure Container Apps (front end,
simulator API, agents API, MCP server) with a user-assigned managed identity
for image pulls and keyless Foundry access, an MCP server the agents call over
streamable HTTP, and Azure AI Foundry behind Microsoft Agent Framework.

## Elevator pitch

Parallel Match lets a fan tap a contestable moment, a borderline penalty or a
tight offside, and ask "what if that call had gone the other way?". The screen
splits into the real match and an alternate match, re-simulated hundreds of
times with paired random numbers so the difference is the call, not luck.
A second opinion comes from the league's own season: comparable decisions and
what followed, and the app says plainly when the two disagree. Four agents on
Microsoft Agent Framework and Azure AI Foundry narrate both timelines, explain
the Law neutrally, cite precedent fetched through an MCP server, and turn free
text into a valid what-if. Every number is computed in code and checked by
guardrails. All data is synthetic. It runs on Azure Container Apps.

## Microsoft technologies used

- **Azure AI Foundry** (model `gpt-4.1-mini`) via **Microsoft Agent Framework**:
  Narrator, Law Explainer, Historian, Intervention Parser (`agents/`)
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
5. Switch to the **Analyst** tab for the evidence: the decision and the Law it
   falls under, outcome shares, alternate final scores, the Historian's season
   precedent (fetched through the MCP server) and whether it agrees with the
   simulation, and the divergence log.
6. Try another match and moment. Featured moments answer in about a second;
   other moments are simulated live: up to about 15 seconds for an early
   moment, less for later ones.
7. Use the language menu in the top bar to switch the interface between 18
   languages (English, Spanish, Portuguese, French, German, Italian, Dutch,
   Polish, Russian, Turkish, Arabic, Hindi, Indonesian, Thai, Vietnamese,
   Chinese, Japanese, Korean). A language screen appears on first visit, and
   the agent text (commentary, Law, precedent, free-text "what if") follows
   the choice. Output is checked for numbers and neutral wording before it is
   shown; if a check fails the English text is served with a note.

Service health, for the curious: https://pm-agents.agreeableflower-13af161d.japaneast.azurecontainerapps.io/health shows the model provider
(Foundry) and the MCP connection. MCP endpoint (streamable HTTP):
https://pm-history-mcp.agreeableflower-13af161d.japaneast.azurecontainerapps.io/mcp.
