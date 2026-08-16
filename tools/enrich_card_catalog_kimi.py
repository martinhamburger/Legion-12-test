#!/usr/bin/env python3
"""Pre-fill review-gated card fields with Kimi vision; never auto-verify them."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = """Read this Chinese game-card image. Return exactly one JSON object.
Do not invent unreadable text; return null and state uncertainty in notes. Preserve
Chinese wording exactly when legible. This is a candidate import, never a rules
interpretation. Required JSON:
{"official_card_id":string|null,"name":string|null,
"card_type":"legion"|"master"|"divinity"|"disaster"|"special"|"other"|null,
"cost":integer|null,"stats":{"troops":integer|null,"health":integer|null,"blood":integer|null},
"text":string|null,"tags":[string],"notes":string,
"field_confidence":{"official_card_id":number,"name":number,"card_type":number,"cost":number,"stats":number,"text":number}}
All confidence values must be between 0 and 1."""
ALLOWED_TYPES = {"legion", "master", "divinity", "disaster", "special", "other"}
CARD_ID = re.compile(r"^[A-Za-z0-9-]{3,32}$")


class KimiRequestError(RuntimeError):
    """The API response cannot safely be stored."""


def load_env(path: Path) -> dict[str, str]:
    """Read a small private KEY=VALUE config; shell variables take precedence."""

    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL", "KIMI_WORKERS"):
        if os.getenv(key):
            values[key] = os.environ[key]
    return values


def parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise KimiRequestError(f"model response is not JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise KimiRequestError("model response must be a JSON object")
    return payload


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate untrusted LLM output before it reaches the card catalog."""

    result: dict[str, Any] = {
        "official_card_id": None,
        "name": None,
        "card_type": None,
        "cost": None,
        "stats": {},
        "text": None,
        "tags": [],
        "notes": "",
        "field_confidence": {},
    }
    official_id = candidate.get("official_card_id")
    if isinstance(official_id, str) and CARD_ID.fullmatch(official_id.strip()):
        result["official_card_id"] = official_id.strip().upper()
    for field in ("name", "text", "notes"):
        value = candidate.get(field)
        if isinstance(value, str) and value.strip():
            result[field] = value.strip()
    if candidate.get("card_type") in ALLOWED_TYPES:
        result["card_type"] = candidate["card_type"]
    if isinstance(candidate.get("cost"), int) and 0 <= candidate["cost"] <= 99:
        result["cost"] = candidate["cost"]
    if isinstance(candidate.get("stats"), dict):
        result["stats"] = {
            str(key): value
            for key, value in candidate["stats"].items()
            if isinstance(value, int) and 0 <= value <= 1_000_000
        }
    if isinstance(candidate.get("tags"), list):
        result["tags"] = [str(tag).strip() for tag in candidate["tags"] if str(tag).strip()][:20]
    if isinstance(candidate.get("field_confidence"), dict):
        result["field_confidence"] = {
            str(key): float(value)
            for key, value in candidate["field_confidence"].items()
            if isinstance(value, (int, float)) and 0 <= float(value) <= 1
        }
    return result


def image_data_url(path: Path) -> str:
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def call_kimi(config: dict[str, str], image: Path, card_id: str) -> tuple[dict[str, Any], str]:
    endpoint = f"{config['KIMI_BASE_URL'].rstrip('/')}/chat/completions"
    body = {
        "model": config["KIMI_MODEL"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_data_url(image)}},
                {"type": "text", "text": f"Extract card {card_id} as JSON."},
            ]},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {config['KIMI_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise KimiRequestError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise KimiRequestError(f"network error: {exc.reason}") from exc
    try:
        raw = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise KimiRequestError("response does not contain choices[0].message.content") from exc
    if not isinstance(raw, str):
        raise KimiRequestError("response content is not text")
    return normalize_candidate(parse_json(raw)), raw


def apply_candidate(card: dict[str, Any], candidate: dict[str, Any], raw: str, model: str) -> None:
    """Merge candidate fields while retaining the review gate and raw response."""

    for field in ("official_card_id", "name", "card_type", "cost", "text", "tags"):
        if candidate[field] is not None and candidate[field] != []:
            card[field] = candidate[field]
    if candidate["stats"]:
        card["stats"] = candidate["stats"]
    card["ocr"]["field_confidence"] = candidate["field_confidence"]
    card["llm"] = {
        "provider": "kimi",
        "model": model,
        "processed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "raw_response": raw,
        "notes": candidate["notes"],
    }
    card["review"] = {
        **card["review"],
        "status": "needs_review",
        "notes": "Kimi vision prefill; verify every extracted field against the card image.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-fill a card pool with Kimi vision candidates.")
    parser.add_argument("--catalog", type=Path, default=Path("data/card_pools/s01/card_pool.json"))
    parser.add_argument("--image-dir", type=Path, default=Path("build/review-site/cards"))
    parser.add_argument("--env-file", type=Path, default=Path(".env.kimi"))
    parser.add_argument("--workers", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_env(args.env_file)
    required = ("KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL")
    missing = [key for key in required if not config.get(key)]
    if missing and not args.dry_run:
        raise SystemExit(f"missing {', '.join(missing)}; copy .env.kimi.example to .env.kimi first")
    workers = args.workers or int(config.get("KIMI_WORKERS", "2"))
    if not 1 <= workers <= 8:
        raise SystemExit("workers must be between 1 and 8")
    pool = json.loads(args.catalog.read_text(encoding="utf-8"))
    pending = [card for card in pool["cards"] if args.retry_failed or card.get("llm", {}).get("provider") != "kimi"]
    if args.limit is not None:
        pending = pending[: args.limit]
    missing_images = [card["card_id"] for card in pending if not (args.image_dir / f"{card['card_id']}.webp").exists()]
    if missing_images:
        raise SystemExit("missing preview images; run: python tools/build_review_site.py")
    print(f"pending={len(pending)} workers={workers} catalog={args.catalog}")
    if args.dry_run:
        return 0

    def process(card: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
        candidate, raw = call_kimi(config, args.image_dir / f"{card['card_id']}.webp", card["card_id"])
        return card, candidate, raw

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process, card): card for card in pending}
        for index, future in enumerate(as_completed(futures), start=1):
            card = futures[future]
            try:
                _, candidate, raw = future.result()
                apply_candidate(card, candidate, raw, config["KIMI_MODEL"])
                args.catalog.write_text(json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"[{index}/{len(pending)}] ok {card['card_id']}")
            except KimiRequestError as exc:
                failures.append(f"{card['card_id']}: {exc}")
                print(f"[{index}/{len(pending)}] failed {failures[-1]}", file=sys.stderr)
    if failures:
        print("failed cards:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
