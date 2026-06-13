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
        raise ValueError("画像 JSON 必须是符合 config/interests.json schema 的对象。")
    _validate_profile_payload(payload)
    return payload


def write_profile_payload(payload: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写入已验证的兴趣画像 JSON 覆盖文件。")
    parser.add_argument("--from-env", required=True, help="包含画像 JSON 的环境变量。")
    parser.add_argument("--output", required=True, help="输出画像 JSON 路径。")
    args = parser.parse_args(argv)

    payload = profile_payload_from_json_text(_required_env(args.from_env))
    write_profile_payload(payload, args.output)
    print(f"已写入兴趣画像覆盖文件：{args.output}")
    return 0


def _validate_profile_payload(payload: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "interests.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        load_interest_profile(path)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"缺少必要环境变量：{name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
