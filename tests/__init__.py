
import os

# No background cache warm-up while tests run (agents/server.py).
os.environ.setdefault("PM_WARM", "0")
