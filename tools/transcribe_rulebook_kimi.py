#!/usr/bin/env python3
"""Transcribe any page-level rulebook JSON with Kimi vision for human review."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from enrich_card_catalog_kimi import KimiRequestError, load_env
from enrich_rules_kimi import call_kimi


def render_page(pdf: Path, page: int, directory: Path) -> Path:
    prefix = directory / f"page-{page:03d}"
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "165", "-jpeg", str(pdf), str(prefix)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return next(directory.glob(f"page-{page:03d}-*.jpg"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe a page-level rulebook with Kimi vision.")
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env.kimi"))
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    config = load_env(args.env_file)
    missing = [key for key in ("KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL") if not config.get(key)]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)}; configure {args.env_file} first")
    payload = json.loads(args.rules.read_text(encoding="utf-8"))
    pending = [entry for entry in payload["rules"] if args.retry or not entry.get("llm", {}).get("provider") == "kimi"]
    print(f"pending={len(pending)} rules={args.rules}")
    with tempfile.TemporaryDirectory(prefix="legion12-rulebook-vision-") as temporary:
        directory = Path(temporary)
        for index, entry in enumerate(pending, start=1):
            page = entry["source"]["page"]
            image = render_page(args.pdf, page, directory)
            try:
                candidate, raw = call_kimi(config, image, entry["rule_id"])
            except KimiRequestError as exc:
                raise SystemExit(f"{entry['rule_id']}: {exc}") from exc
            entry["title"] = candidate["title"]
            entry["text"] = candidate["text"]
            entry["llm"] = {
                "provider": "kimi",
                "model": config["KIMI_MODEL"],
                "processed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "raw_response": raw,
                "notes": candidate["notes"],
            }
            entry["review"] = {
                **entry["review"],
                "status": "needs_review",
                "notes": "Kimi vision transcription of historical handbook; verify against the original screenshot.",
            }
            args.rules.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[{index}/{len(pending)}] ok {entry['rule_id']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
