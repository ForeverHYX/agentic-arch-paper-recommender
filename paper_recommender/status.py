"""Publish non-secret deployment status for the static reader."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def deployment_status() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "llm": {
            "configured": _env_bool("HAS_LLM"),
            "base_url": os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL,
            "model": os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL,
        },
        "smtp": {"configured": _env_bool("HAS_SMTP")},
        "supabase": {"configured": _env_bool("HAS_SUPABASE")},
        "local_feedback": {"configured": _env_bool("HAS_LOCAL_FEEDBACK")},
        "profile_override": {"configured": _env_bool("HAS_PROFILE_OVERRIDE")},
    }


def write_status_json(output_path: str | Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    status = payload or deployment_status()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write non-secret Pages deployment status JSON.")
    parser.add_argument("--output", required=True, help="Output status JSON path.")
    args = parser.parse_args(argv)

    write_status_json(args.output)
    print(f"Wrote deployment status to {args.output}")
    return 0


def _env_bool(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().casefold() == "true"


if __name__ == "__main__":
    raise SystemExit(main())
