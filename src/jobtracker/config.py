"""Configuration: role-type rules, follow-up intervals and sources. Read from a TOML file; defaults work without one."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

DEFAULTS: dict = {
    # first matching rule wins; keywords are matched against the lower-cased job title
    "role_types": [
        {"name": "ml-engineering", "keywords": ["machine learning engineer", "ml engineer", "mlops"]},
        {"name": "data-science", "keywords": ["data scientist", "data science"]},
        {"name": "analytics", "keywords": ["analyst", "analytics"]},
        {"name": "software", "keywords": ["software engineer", "developer", "backend"]},
    ],
    "default_role_type": "other",
    # days after the last update before a follow-up is due, per status
    "follow_up_days": {"applied": 7, "screen": 3, "interview": 2, "offer": 2},
    # applications still "applied" after this many days count as no response
    "ghost_after_days": 21,
    "sources": ["job-board", "company-site", "referral", "recruiter", "other"],
    # words dropped from company names before de-duplication
    "company_suffixes": ["inc", "llc", "ltd", "limited", "pvt", "private", "corp", "corporation", "co", "gmbh",
                         "plc", "technologies", "technology", "solutions"],
}


def load_config(path: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"config not found: {p}")
        with open(p, "rb") as f:
            cfg.update(tomllib.load(f))
    return cfg


def role_type(title: str, cfg: dict) -> str:
    t = title.lower()
    for rule in cfg["role_types"]:
        if any(k.lower() in t for k in rule["keywords"]):
            return rule["name"]
    return cfg["default_role_type"]
