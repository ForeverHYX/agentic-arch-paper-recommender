"""Helpers for loading an interest profile override from GitHub Actions secrets."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from paper_recommender.domain import load_interest_profile


def profile_payload_from_json_text(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Profile JSON must be an object using the config/interests.json schema.")
    _validate_profile_payload(payload)
    return payload


def write_profile_payload(payload: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a validated interest profile JSON override.")
    parser.add_argument("--from-env", required=True, help="Environment variable containing profile JSON.")
    parser.add_argument("--output", required=True, help="Output profile JSON path.")
    args = parser.parse_args(argv)

    payload = profile_payload_from_json_text(_required_env(args.from_env))
    write_profile_payload(payload, args.output)
    print(f"Wrote interest profile override to {args.output}")
    return 0


def _validate_profile_payload(payload: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "interests.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        load_interest_profile(path)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
