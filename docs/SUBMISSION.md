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
- [x] Hosting confirmed with `./deploy/deploy.sh status` (pm-api 2 vCPU, every
  app min 1 replica, about $44 to 10 Nov, inside the $100 credit); output in
  `docs/deployment.md` (25 Oct)
- [x] Foundry on: agents `/health` shows `agent-framework/foundry`, model
  `gpt-4.1-mini`, no model error; Narrator text is model-phrased (24 Oct)
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

- **Azure AI Foundry** (model: as printed by `deploy.sh foundry-create`, normally `gpt-4.1-mini`) via **Microsoft Agent Framework**:
  Narrator, Law Explainer, Historian, Intervention Parser (`agents/`)
- **MCP**: `history_query` / `season_summary` server on Container Apps; the
  Historian fetches its facts through it (`mcp_history/`, `agents/history_client.py`)
- **Azure Container Apps**: four apps, user-assigned managed identity, Azure
  Container Registry (`deploy/`)
<!-- Claim these two only if true:
- GitHub Copilot: add a line only if the team used it while building.
- Microsoft Fabric: add "season decisions in a Fabric Lakehouse; the precedent
  query runs on its SQL analytics endpoint with the same result as the app"
  only once docs/fabric.md step 3 has matched, with docs/img/fabric-precedent-m052.png.
-->

## Testing instructions (for judges)

No login needed. Works on desktop and phone.

1. Open https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
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

Service health, for the curious: https://pm-agents.agreeableflower-13af161d.japaneast.azurecontainerapps.io/health shows the model provider
(Foundry) and the MCP connection. MCP endpoint (streamable HTTP):
https://pm-history-mcp.agreeableflower-13af161d.japaneast.azurecontainerapps.io/mcp.

## Links

- Live demo: https://pm-web.agreeableflower-13af161d.japaneast.azurecontainerapps.io
- Video: <YouTube URL>
- Repo: https://github.com/evanyap7/the-parallel-match
