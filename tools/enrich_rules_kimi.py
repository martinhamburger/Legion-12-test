#!/usr/bin/env python3
"""Transcribe rendered rulebook pages with Kimi vision for human review."""

from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from enrich_card_catalog_kimi import KimiRequestError, load_env, parse_json


PROMPT = """Read this rendered Chinese game rulebook page. Return exactly one JSON object:
{"title": string, "text": string, "notes": string}
Transcribe every legible heading, paragraph, list and rule statement on this image.
Preserve Chinese wording and paragraph breaks. Do not summarize, infer missing wording,
or add game-rule interpretations. If a small fragment is unreadable, use [不清晰]."""


def image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suffix)
    if mime is None:
        raise KimiRequestError(f"unsupported rule image format: {path.suffix}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def call_kimi(config: dict[str, str], image: Path, rule_id: str) -> tuple[dict[str, str], str]:
    endpoint = f"{config['KIMI_BASE_URL'].rstrip('/')}/chat/completions"
    body = {
        "model": config["KIMI_MODEL"],
        "temperature": 0.6,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url(image)}},
                    {"type": "text", "text": f"Transcribe rule entry {rule_id}."},
                ],
            },
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {config['KIMI_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
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
    candidate = parse_json(raw)
    title = candidate.get("title")
    text = candidate.get("text")
    notes = candidate.get("notes")
    if not isinstance(title, str) or not title.strip() or not isinstance(text, str) or not text.strip():
        raise KimiRequestError("response must include non-empty title and text")
    return {"title": title.strip(), "text": text.strip(), "notes": str(notes or "").strip()}, raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe rulebook page previews with Kimi vision.")
    parser.add_argument("--rules", type=Path, default=Path("data/card_pools/s01/rules.json"))
    parser.add_argument("--image-dir", type=Path, default=Path("build/review-site/rules"))
    parser.add_argument("--env-file", type=Path, default=Path(".env.kimi"))
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    config = load_env(args.env_file)
    missing = [key for key in ("KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL") if not config.get(key)]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)}; configure .env.kimi first")
    rulebook = json.loads(args.rules.read_text(encoding="utf-8"))
    pending = [rule for rule in rulebook["rules"] if args.retry or not rule.get("llm", {}).get("provider") == "kimi"]
    images = {rule["rule_id"]: args.image_dir / f"{rule['rule_id']}.webp" for rule in pending}
    missing_images = [rule_id for rule_id, image in images.items() if not image.exists()]
    if missing_images:
        raise SystemExit("missing rule previews; run: python tools/build_review_site.py")
    print(f"pending={len(pending)} rules={args.rules}")
    for index, rule in enumerate(pending, start=1):
        candidate, raw = call_kimi(config, images[rule["rule_id"]], rule["rule_id"])
        rule["title"] = candidate["title"]
        rule["text"] = candidate["text"]
        rule["llm"] = {
            "provider": "kimi",
            "model": config["KIMI_MODEL"],
            "processed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "raw_response": raw,
            "notes": candidate["notes"],
        }
        rule["review"] = {
            **rule["review"],
            "status": "needs_review",
            "notes": "Kimi vision transcription; verify against the rulebook screenshot.",
        }
        args.rules.write_text(json.dumps(rulebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[{index}/{len(pending)}] ok {rule['rule_id']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
