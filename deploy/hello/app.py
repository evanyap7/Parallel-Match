"""Hello-world service: first container onto Azure Container Apps.

Deployment is the riskiest step in the plan, so this goes up first to flush
out registry, ingress and identity problems while everything else is still
local. Delete it once the real services are green.
"""

from fastapi import FastAPI

app = FastAPI(title="the-home-dugout hello")


@app.get("/")
def root():
    return {"hello": "the-home-dugout", "service": "hello-world", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
