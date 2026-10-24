"""Fictional league: clubs, styles, formations and generated players.

Every name here is invented. Club styles follow real tactical archetypes
(possession, high press, counter-attack, direct, low block) without copying
any real club.
"""

from dataclasses import dataclass

from .rng import Rng

# Formation slots in the team's attacking frame: (role, ax, y).
# ax = metres from own goal line, y = metres across.
FORMATIONS = {
    "4-4-2": [
        ("GK", 4, 34),
        ("DEF", 22, 10), ("DEF", 20, 26), ("DEF", 20, 42), ("DEF", 22, 58),
        ("MID", 45, 10), ("MID", 42, 27), ("MID", 42, 41), ("MID", 45, 58),
        ("FWD", 66, 28), ("FWD", 66, 40),
    ],
    "4-3-3": [
        ("GK", 4, 34),
        ("DEF", 22, 10), ("DEF", 20, 26), ("DEF", 20, 42), ("DEF", 22, 58),
        ("MID", 40, 20), ("MID", 38, 34), ("MID", 40, 48),
        ("FWD", 66, 12), ("FWD", 70, 34), ("FWD", 66, 56),
    ],
    "4-2-3-1": [
        ("GK", 4, 34),
        ("DEF", 22, 10), ("DEF", 20, 26), ("DEF", 20, 42), ("DEF", 22, 58),
        ("MID", 36, 26), ("MID", 36, 42),
        ("MID", 55, 12), ("MID", 56, 34), ("MID", 55, 56),
        ("FWD", 70, 34),
    ],
    "3-5-2": [
        ("GK", 4, 34),
        ("DEF", 20, 18), ("DEF", 19, 34), ("DEF", 20, 50),
        ("MID", 44, 6), ("MID", 40, 24), ("MID", 38, 34), ("MID", 40, 44), ("MID", 44, 62),
        ("FWD", 66, 28), ("FWD", 66, 40),
    ],
    "5-3-2": [
        ("GK", 4, 34),
        ("DEF", 24, 6), ("DEF", 19, 20), ("DEF", 18, 34), ("DEF", 19, 48), ("DEF", 24, 62),
        ("MID", 40, 18), ("MID", 38, 34), ("MID", 40, 50),
        ("FWD", 64, 28), ("FWD", 64, 40),
    ],
}

BENCH_ROLES = ("GK", "DEF", "DEF", "MID", "MID", "FWD", "FWD")

# code, name, formation, quality, attack, defence, press, tempo, directness, archetype
CLUB_TABLE = [
    ("HAR", "Harbourside Rovers", "4-3-3", 0.66, 0.70, 0.62, 0.75, 0.60, 0.25, "possession, high press"),
    ("NOR", "Northgate Athletic", "4-2-3-1", 0.63, 0.65, 0.58, 0.85, 0.80, 0.45, "gegenpress, fast tempo"),
    ("STO", "Stonebridge City", "4-3-3", 0.64, 0.62, 0.66, 0.55, 0.45, 0.20, "patient possession"),
    ("KES", "Kestrel Wanderers", "4-2-3-1", 0.58, 0.55, 0.58, 0.55, 0.55, 0.45, "balanced"),
    ("BRW", "Brightwater Albion", "3-5-2", 0.57, 0.72, 0.42, 0.60, 0.70, 0.50, "all-out attack"),
    ("RED", "Redmere Town", "4-4-2", 0.55, 0.50, 0.65, 0.35, 0.65, 0.65, "counter-attack"),
    ("IRO", "Ironvale United", "4-4-2", 0.54, 0.52, 0.60, 0.50, 0.55, 0.80, "direct, physical"),
    ("WES", "Westfield Rangers", "5-3-2", 0.52, 0.38, 0.72, 0.30, 0.40, 0.55, "low block"),
    ("LAR", "Larkhill Borough", "3-5-2", 0.51, 0.55, 0.45, 0.60, 0.75, 0.70, "direct, high tempo"),
    ("COP", "Copperfield FC", "4-4-2", 0.50, 0.48, 0.52, 0.45, 0.50, 0.50, "balanced, underdog"),
]

ROLE_BIAS = {
    #        finishing passing dribbling tackling saving
    "GK":  (-0.40, -0.05, -0.30, -0.30, 0.08),
    "DEF": (-0.20, 0.00, -0.10, 0.12, -0.50),
    "MID": (-0.05, 0.10, 0.03, 0.00, -0.50),
    "FWD": (0.15, -0.04, 0.10, -0.22, -0.50),
}

_SYL = ("ka", "lo", "ven", "dri", "mar", "tel", "so", "ran", "bek", "quil",
        "or", "fen", "ash", "tor", "vi", "nel", "dun", "ree", "gal", "cor",
        "bas", "wyn", "el", "ma", "tho", "jun", "pel", "ris", "ad", "hol")


@dataclass(frozen=True, slots=True)
class Player:
    id: str          # club initial + shirt number, e.g. "H7"
    name: str
    pos: str         # GK / DEF / MID / FWD
    number: int
    finishing: float
    passing: float
    dribbling: float
    tackling: float
    saving: float
    stamina: float
    discipline: float


@dataclass(frozen=True, slots=True)
class Club:
    code: str
    name: str
    formation: str
    archetype: str
    quality: float
    attack: float
    defence: float
    press: float
    tempo: float
    directness: float
    squad: tuple[Player, ...]  # first 11 are starters in formation slot order

    def style(self) -> dict:
        return {"attack": self.attack, "defence": self.defence, "press": self.press,
                "tempo": self.tempo, "directness": self.directness}


def _clamp(v, lo=0.05, hi=0.98):
    return lo if v < lo else hi if v > hi else v


def _name(rng: Rng) -> str:
    def word(n):
        return "".join(_SYL[int(rng.u() * len(_SYL))] for _ in range(n)).capitalize()
    return f"{word(2)} {word(2 + int(rng.u() * 2))}"


def _make_player(rng: Rng, code: str, number: int, role: str, quality: float) -> Player:
    bias = ROLE_BIAS[role]
    f, p, d, t, s = (_clamp(quality + b + rng.normal(0, 0.07)) for b in bias)
    return Player(
        id=f"{code[0]}{number}", name=_name(rng), pos=role, number=number,
        finishing=round(f, 3), passing=round(p, 3), dribbling=round(d, 3),
        tackling=round(t, 3), saving=round(s, 3),
        stamina=round(_clamp(rng.normal(0.62, 0.12)), 3),
        discipline=round(_clamp(rng.normal(0.58, 0.15)), 3),
    )


def build_league(world_seed: int = 2026) -> list[Club]:
    clubs = []
    for ci, (code, name, formation, q, att, dfn, prs, tmp, drc, arch) in enumerate(CLUB_TABLE):
        roles = [r for r, _, _ in FORMATIONS[formation]] + list(BENCH_ROLES)
        squad = []
        for pi, role in enumerate(roles):
            rng = Rng(world_seed, 10_000 + ci * 100 + pi)
            # Starters wear 1..11, bench GK 13, other subs 15..20.
            number = pi + 1 if pi < 11 else (13 if pi == 11 else pi + 3)
            squad.append(_make_player(rng, code, number, role, q))
        clubs.append(Club(code, name, formation, arch, q, att, dfn, prs, tmp, drc, tuple(squad)))
    return clubs


def club_by_code(clubs: list[Club], code: str) -> Club:
    for c in clubs:
        if c.code == code:
            return c
    raise KeyError(f"unknown club {code!r}")
