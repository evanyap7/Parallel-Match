# Submission draft (Inside the Game hackathon)

Paste-ready text for the form at aka.ms/insidethegame (Projects page). Only
the video link is still to fill in. Rules: github.com/microsoft/insidethegamehackathon,
OFFICIAL RULES.md.

**Deadline: 27 Oct 2026, 11:59 pm PT = Wed 28 Oct, 2:59 pm Singapore.**
The site must stay up and free to use until judging ends: **10 Nov, 11:59 pm PT**.

## Checklist

- [ ] Team registered (registration closed 20 Oct)
- [ ] Category chosen and named in the pitch (one category prize per project)
- [x] Live link works (`./deploy/smoke.sh` all ok, 24 Oct)
- [ ] Live link checked on a phone on mobile data
- [ ] Foundry on (agents `/health` shows `agent-framework/foundry`)
- [ ] Video under 2 minutes, public on YouTube or Vimeo, no copyrighted music
- [ ] Repo public, README "Live demo" link filled in, stack table says "live"
- [ ] Everything in English

## Category

We enter **Best Azure Cloud Native Integration**: four Azure Container Apps
(front end, simulator API, agents API, MCP server) with a user-assigned managed
identity for image pulls and keyless Foundry access, an MCP server the agents
call over streamable HTTP, and Azure AI Foundry behind Microsoft Agent
Framework. *(Team to confirm. Alternatives: Best Use of Microsoft Foundry,
Best Multi-Agent System.)*

## Elevator pitch (about 120 words)

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

- **Azure AI Foundry** (model `gpt-4o-mini`) via **Microsoft Agent Framework**:
  Narrator, Law Explainer, Historian, Intervention Parser (`agents/`)
- **MCP**: `history_query` / `season_summary` server on Container Apps; the
  Historian fetches its facts through it (`mcp_history/`, `agents/history_client.py`)
- **Azure Container Apps**: four apps, user-assigned managed identity, Azure
  Container Registry (`deploy/`)
- **GitHub Copilot**: list it only if the team actually used it; otherwise
  delete this line.
- **Microsoft Fabric**: list it only once `docs/fabric.md` step 3 has been
  run and matched (screenshot in `docs/img/`). Then: "season decisions in a
  Fabric Lakehouse; the precedent query runs on its SQL analytics endpoint with
  the same result as the app". Otherwise delete this line.

## Testing instructions (for judges)

No login needed.

1. Open https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
2. Choose match **m052** (Westfield Rangers 2-1 Copperfield FC) and tap the
   penalty at **56'**.
3. Type "what if that was not a penalty?" in the what-if box. The
   split screen shows both timelines; the result card shows the change in win
   share with its 95% interval.
4. Read the agent panels: Narrator (both timelines), Law Explainer (Law 12 and
   how close the decision was), Historian (season precedent, fetched via MCP,
   and whether it agrees with the simulation).
5. Try any other match and moment. Featured moments answer in about a
   second; other moments are simulated live and take about 15 seconds.

Service health, for the curious: https://pm-agents.agreeableflower-13af161d.japaneast.azurecontainerapps.io/health shows the model provider
(Foundry) and the MCP connection. MCP endpoint (streamable HTTP):
https://pm-history-mcp.agreeableflower-13af161d.japaneast.azurecontainerapps.io/mcp.

## Links

- Live demo: https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
- Video: <YouTube URL>
- Repo: https://github.com/evanyap7/the-home-dugout
