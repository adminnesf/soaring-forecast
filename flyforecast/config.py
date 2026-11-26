"""Load the site list and settings."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"  # built web page (deployed to GitHub Pages, not committed)

FT_PER_M = 3.28084


def load_settings():
    with open(CONFIG_DIR / "settings.yaml") as f:
        return yaml.safe_load(f)


def load_sites(filename="sites.yaml"):
    with open(CONFIG_DIR / filename) as f:
        sites = yaml.safe_load(f)["sites"]
    for s in sites:
        s.setdefault("windows", [])
        s.setdefault("no_fly", [])
        s.setdefault("ushpa", True)
        s.setdefault("notes", "")
        s["launch_m"] = s["launch_ft"] / FT_PER_M
        s["ground_m"] = s["ground_ft"] / FT_PER_M
    return sites
