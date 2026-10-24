"""Parallel Match: seeded, forkable, event-level football simulator.

All clubs, players and matches are synthetic.
"""

from .sim import MatchRecord, new_match, play, simulate, step
from .state import MatchState
from .teams import build_league, club_by_code

__all__ = ["MatchRecord", "MatchState", "build_league", "club_by_code",
           "new_match", "play", "simulate", "step"]
