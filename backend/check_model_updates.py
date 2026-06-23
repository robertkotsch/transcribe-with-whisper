"""Update checker for the models configured in models.config.json.

Report-only: queries the Ollama registry for each configured text/VLM model and
reports whether the locally-installed copy is current, plus whether a newer
named version of the same family exists. Makes no changes.

Usage:
    python backend/check_model_updates.py

This lives in Python (not Update-Models.ps1) on purpose: a PowerShell script that
downloads from a URL trips Windows Defender's malware-downloader heuristic and
gets quarantined. The Python backend already makes HTTP calls, so it is safe here.
"""
import json
import os
import re
import sys

import requests

REGISTRY = "https://registry.ollama.ai/v2/library"
MODEL_LAYER = "application/vnd.ollama.image.model"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "models.config.json")


def remote_layer_digest(name: str, tag: str):
    """Model-layer digest for name:tag from the registry, or None if absent."""
    try:
        r = requests.get(
            f"{REGISTRY}/{name}/manifests/{tag}",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            timeout=10,
        )
        if not r.ok:
            return None
        for layer in r.json().get("layers", []):
            if layer.get("mediaType") == MODEL_LAYER:
                return layer.get("digest")
    except Exception:
        return None
    return None


def local_layer_digest(name: str, tag: str):
    """Model-layer digest for an installed model, or None if not installed."""
    models_dir = os.environ.get("OLLAMA_MODELS") or os.path.join(os.path.expanduser("~"), ".ollama", "models")
    path = os.path.join(models_dir, "manifests", "registry.ollama.ai", "library", name, tag)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for layer in json.load(f).get("layers", []):
                if layer.get("mediaType") == MODEL_LAYER:
                    return layer.get("digest")
    except Exception:
        return None
    return None


def successor_candidates(family: str):
    """Bump the first version number in a model name, keeping prefix/suffix
    (qwen3.5 -> qwen3.6/qwen4; qwen3-vl -> qwen3.5-vl/qwen4-vl)."""
    m = re.match(r"^(?P<prefix>.*?)(?P<ver>\d+(?:\.\d+)?)(?P<suffix>.*)$", family)
    if not m:
        return []
    prefix, ver, suffix = m.group("prefix"), m.group("ver"), m.group("suffix")
    vers = []
    if "." in ver:
        maj, minor = (int(x) for x in ver.split("."))
        vers += [f"{maj}.{minor + i}" for i in (1, 2, 3)]
        vers += [str(maj + 1), str(maj + 2)]
    else:
        maj = int(ver)
        vers += [f"{maj}.5", str(maj + 1), f"{maj + 1}.5", str(maj + 2)]
    seen, out = set(), []
    for v in vers:
        cand = f"{prefix}{v}{suffix}"
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


def main():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            tiers = json.load(f).get("tiers", [])
    except Exception as e:
        print(f"ERROR: could not read {CONFIG_PATH}: {e}")
        return 1

    models = sorted({m for t in tiers for m in (t.get("text"), t.get("vlm")) if m})
    print(f"Checking {len(models)} configured models against the Ollama registry...\n")

    for model in models:
        name, _, tag = model.partition(":")
        tag = tag or "latest"
        remote = remote_layer_digest(name, tag)
        local = local_layer_digest(name, tag)

        if remote is None:
            status = "NOT FOUND in registry (typo in config?)"
        elif local is None:
            status = "not installed - run Update-Models.ps1 to pull"
        elif local != remote:
            status = "UPDATE AVAILABLE - tag rebuilt upstream; run pull to refresh"
        else:
            status = "up to date"
        print(f"  {model:<16} {status}")

        found = [f"{c}:{tag}" for c in successor_candidates(name) if remote_layer_digest(c, tag)]
        if found:
            print(f"       newer version available: {', '.join(found)}")

    print("\nNewer-version detection probes common name patterns; review before editing models.config.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
