#!/usr/bin/env python3
"""Create the review-gated S1 data sets used by the first matchup.

The source values in this file were transcribed from the user-supplied card
image and the official PDF pages.  Running it is idempotent: it updates the
catalogue entry for S01-0002 and rewrites only the generated S1 data files.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/card_pools/s01/card_pool.json"
OUTPUT = ROOT / "data/s1"
RULESETS = ROOT / "data/rulesets"
PDF_DIR = ROOT / "规则与卡池"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source(path: str, page: int | None = None) -> dict[str, object]:
    file = ROOT / path
    payload: dict[str, object] = {"asset_path": path, "asset_sha256": sha256(file)}
    if path.lower().endswith(".pdf"):
        payload["kind"] = "pdf_page"
        payload["pdf_path"] = path
        payload["pdf_sha256"] = payload["asset_sha256"]
        payload["page"] = page
    else:
        payload["kind"] = "image"
        payload["image_path"] = path
        payload["image_sha256"] = payload["asset_sha256"]
    return payload


def effect() -> dict[str, object]:
    return {"dsl_version": "0.1", "implementation_status": "not_started", "operations": []}


def review(notes: str) -> dict[str, object]:
    return {"status": "needs_review", "reviewed_fields": [], "notes": notes}


def card_engine_type(card: dict[str, object]) -> str:
    card_type = card.get("card_type")
    tags = set(card.get("tags", []))
    if card_type == "master":
        return "ruler"
    if card_type == "legion":
        return "unit"
    if card_type == "divinity":
        return "city"
    if "士气卡" in tags:
        return "faction_morale"
    if "衍生卡" in tags or "TOKEN" in tags:
        return "token"
    if "圣物" in tags:
        return "artifact"
    if "反击" in tags:
        return "tactic_counter"
    if "战术" in tags or "主动" in tags:
        return "tactic_active"
    return "unmodeled"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_catalog() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    cards = [card for card in payload["cards"] if card.get("official_card_id") != "S01-0002"]
    cards.append(
        {
            "card_id": "S01-0002",
            "official_card_id": "S01-0002",
            "name": "佣兵部队",
            "faction": {"id": "common", "label": "通用"},
            "card_type": "legion",
            "engine_card_type": "unit",
            "cost": 4,
            "stats": {"troops": 5000},
            "text": "我方回合1次：可进行1次位移。\n对方进攻我方军团时，可从手牌中弃置此军团：抵挡本次进攻。",
            "tags": ["骑兵", "通用"],
            "effect": effect(),
            "ocr": {
                "engine": "user_supplied_image",
                "raw_text": "",
                "field_confidence": {"official_card_id": 1.0, "name": 1.0, "card_type": 1.0, "cost": 1.0, "stats": 1.0, "text": 1.0},
            },
            "review": review("Supplementary card image transcribed for review; not trainable until approved."),
            "source": source("规则与卡池/补充卡面/S01-0002-佣兵部队.png"),
        }
    )
    for card in cards:
        card["engine_card_type"] = card_engine_type(card)
    payload["cards"] = sorted(cards, key=lambda card: str(card["card_id"]))
    sources = payload.setdefault("sources", [])
    supplementary = "规则与卡池/补充卡面/S01-0002-佣兵部队.png"
    if not any(item.get("path") == supplementary for item in sources):
        sources.append({"path": supplementary, "sha256": sha256(ROOT / supplementary), "kind": "supplementary_card_image"})
    payload["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    write_json(CATALOG, payload)


DISASTERS = [
    ("S01-DS01", "黯陨晨星", "光明与黑暗的分界", "主要阶段开始时，回合玩家掷骰。双数：将我方1张活跃士气转为休整。单数：选择以下一项在本回合中生效：打出《主动战术》无需消耗费用；【术师】位于后排时可攻击对方主宰。", "ongoing", 1, False),
    ("S01-DS02", "百鬼夜行", "妖魔横行 灾厄降临", "触发：对所有主宰造成1点非致命伤害。持续：带有天灾等级的军团进攻主宰时，造成的伤害+1。回合结束时，回合玩家将手牌返回牌库底部，直至手牌数量不高于5。", "trigger_and_ongoing", 1, False),
    ("S01-DS03", "腐移大地", "腐蚀生命的黑暗", "触发：将所有后排军团置入所有者墓地。持续：后排无法放置军团；打出《反击战术》无需消耗费用。", "trigger_and_ongoing", 2, False),
    ("S01-DS04", "雷霆天怒", "吾乃撕裂星辰之雷霆", "触发：所有玩家掷骰，数字最小的玩家选择其1张军团返回所有者手牌。持续：兵力高于2000的军团进攻时需掷骰；1~2：此军团转为休整并结束进攻。", "trigger_and_ongoing", 2, False),
    ("S01-DS05", "魔龙降世", "咆哮天际的咆哮", "触发：回合玩家掷骰。1~2：将其最左侧一列双方战场上的卡牌全部置入墓地；3~4：将其最右侧一列双方战场上的卡牌全部置入墓地；5~6：将中间一列双方战场上的卡牌全部置入墓地。随后所有玩家各将墓地4张卡牌自选顺序返回其牌库底部。", "trigger", 3, False),
    ("S01-DS06", "神之天平", "冥界 生与死的审判", "触发：所有主宰的血量降至与血量最低主宰相等，血量产生变动的玩家抽取2张牌；若没有主宰血量产生变化，则所有玩家抽取1张牌。随后所有玩家弃置1张手牌并抽取1张牌。", "trigger", 3, False),
    ("S01-DS07", "天启默示录", "瘟疫 战争 饥饿与死亡", "触发：所有玩家将其战场上的军团置入所有者墓地，直至不高于2张。随后所有玩家将手牌自选顺序返回牌库底部，并抽取4张牌。", "trigger", 4, False),
    ("S01-DS08", "虚构的圣杯", "来自深渊的低语", "持续：当玩家使用《圣物效果》时，对其主宰造成1点非致命伤害。", "ongoing", 4, False),
    ("S01-DS09", "诸神黄昏", "无法逃避的世界终焉", "触发：将所有军团置入所有者墓地。若为开场触发：所有玩家各抽取2张牌；若为主动触发：其余玩家各抽取2张牌，随后立刻结束当前回合，并为回合玩家追加1个新的回合。", "trigger", 5, False),
    ("S01-DS10", "湮灭", "最终天灾", "持续：回合开始时，对所有主宰造成1点非致命伤害。", "ongoing", 5, True),
]

HISTORICAL_PAGE_TAGS = {
    1: ["cover"],
    2: ["overview", "victory_conditions"],
    3: ["contents"],
    4: ["game_layout", "setup"],
    5: ["card_anatomy", "disaster"],
    6: ["card_anatomy", "ruler", "legion"],
    7: ["card_anatomy", "artifact", "tactic"],
    8: ["card_anatomy", "morale"],
    9: ["core_concepts", "golden_rule", "disaster"],
    10: ["core_concepts", "return_morale", "setup", "disaster_draft"],
    11: ["turn_flow", "morale"],
    12: ["combat"],
    13: ["main_phase", "examples"],
    14: ["deckbuilding", "reference_decks"],
    15: ["variant_rules", "disaster_draft"],
    16: ["faction", "tianting"],
    17: ["faction", "takamagahara"],
    18: ["faction", "asgard"],
    19: ["faction", "sun_city"],
    20: ["credits"],
    21: ["turn_flow", "quick_reference"],
    22: ["back_cover"],
}


def write_s1_content() -> None:
    disaster_source = "规则与卡池/天灾图鉴.pdf"
    disasters = []
    for index, (card_id, name, subtitle, text, timing, page, final) in enumerate(DISASTERS):
        disasters.append(
            {
                "disaster_id": card_id,
                "official_card_id": card_id,
                "name": name,
                "subtitle": subtitle,
                "source_card_type_raw": "天灾",
                "engine_card_type": "disaster",
                "timing": timing,
                "text": text,
                "is_final": final,
                "effect": effect(),
                "review": review("Vision transcription from official disaster catalogue; review before simulation."),
                "source": {**source(disaster_source, page), "crop": {"x": 0.12, "y": 0.06 + (0.43 if index % 2 else 0), "width": 0.76, "height": 0.39}},
            }
        )
    write_json(
        OUTPUT / "disasters.json",
        {
            "schema_version": "1.0",
            "set_id": "s01-disaster-catalogue",
            "game_version": "S1",
            "source": {**source(disaster_source), "pages": 9},
            "cards": disasters,
            "scope": "S01 only; S02 disasters remain source-only.",
        },
    )

    factions = [
        {
            "faction_id": "tianting",
            "label": "天廷",
            "morale_deck_size": 8,
            "resource_definition_id": "S01-01C1",
            "source_card_type_raw": "士气卡",
            "engine_card_type": "faction_morale",
            "variants": ["S01-01C1", "S01-01C1a"],
            "effects": [
                {"limit": "我方回合1次", "cost": [{"op": "pay_morale", "amount": 2}], "operations": [{"op": "add_active_morale", "amount": 1}]},
                {"limit": "我方回合1次", "condition": {"morale_zone_count": 0}, "operations": [{"op": "add_rested_morale", "amount": 2}]},
            ],
            "text": "我方回合1次，可消耗2士气：从士气牌库追加1张活跃的士气。\n我方回合1次，我方士气为0张时，可从士气牌库追加2张休整的士气。",
            "review": review("Official faction morale card; review before simulation."),
            "source": source("规则与卡池/天廷阵营.pdf", 1),
        },
        {
            "faction_id": "takamagahara",
            "label": "高天原",
            "morale_deck_size": 8,
            "resource_definition_id": "S01-04C1",
            "source_card_type_raw": "士气卡",
            "engine_card_type": "faction_morale",
            "variants": ["S01-04C1", "S01-04C1a"],
            "effects": [
                {"limit": "我方回合1次", "cost": [{"op": "pay_morale", "amount": 2}], "operations": [{"op": "draw", "amount": 1}, {"op": "move", "amount": 1, "target": "own_active_unit", "optional": True}]}
            ],
            "text": "我方回合1次，可消耗2士气：抽取1张牌。随后可选择我方1张活跃的军团进行1格位移。",
            "review": review("Official faction morale card; review before simulation."),
            "source": source("规则与卡池/高天原阵营.pdf", 1),
        },
    ]
    write_json(OUTPUT / "faction_resources.json", {"schema_version": "1.0", "game_version": "S1", "factions": factions})

    decks = [
        {
            "deck_id": "s01-tianting-yang-jian-reference",
            "name": "天廷 颂威华夏（杨戬参考构筑）",
            "game_version": "S1",
            "ruleset_id": "standard-2.0-s01",
            "faction_id": "tianting",
            "ruler_official_card_id": "S01-01M1",
            "cards": {"S01-0101": 3, "S01-0102": 3, "S01-0103": 3, "S01-0104": 2, "S01-0105": 2, "S01-0106": 3, "S01-0107": 3, "S01-0108": 2, "S01-0109": 3, "S01-0117": 3, "S01-0118": 2, "S01-0119": 2, "S01-0002": 3, "S01-0012": 2, "S01-0016": 2, "S01-0018": 2},
            "source_ids": ["rules-2.0-source-pdf", "s1-tianting-yang-jian-guide"],
            "review": review("Reference deck preserved for validation; individual effects remain unimplemented."),
        },
        {
            "deck_id": "s01-takamagahara-susanoo-reference",
            "name": "高天原 除魔物语（须佐之男参考构筑）",
            "game_version": "S1",
            "ruleset_id": "standard-2.0-s01",
            "faction_id": "takamagahara",
            "ruler_official_card_id": "S01-04M2",
            "cards": {"S01-0401": 3, "S01-0404": 3, "S01-0405": 3, "S01-0409": 3, "S01-0410": 3, "S01-0413": 2, "S01-0414": 3, "S01-0415": 2, "S01-0416": 1, "S01-0417": 3, "S01-0418": 3, "S01-0419": 3, "S01-0002": 3, "S01-0015": 3, "S01-0016": 2},
            "source_ids": ["rules-2.0-source-pdf"],
            "review": review("Reference deck includes the human-audited correction: 2 copies of 源博雅."),
        },
    ]
    write_json(OUTPUT / "reference_decks.json", {"schema_version": "1.0", "game_version": "S1", "decks": decks})


def write_rulesets() -> None:
    rulebook = "规则与卡池/规则手册2.0.pdf"
    standard = {
        "schema_version": "1.0",
        "ruleset_id": "standard-2.0-s01",
        "display_name": "标准规则 2.0 · S1 首测",
        "game_version": "S1",
        "status": "needs_review",
        "source_priority": [{"source_id": "rules-2.0-source-pdf", "role": "primary"}, {"source_id": "official_card_faces", "role": "card_text_overrides_rules"}],
        "sources": [{"source_id": "rules-2.0-source-pdf", **source(rulebook)}],
        "deck_rules": {"min_main_deck_size": 40, "max_main_deck_size": 50, "max_copies_per_official_id": 3, "limit_one_max_copies": 1, "allowed_factions": ["ruler_faction", "common"]},
        "setup": {"starting_hand_size": 6, "mulligan_count": 1, "first_player_skips_first_draw": True, "first_player_first_morale": 1, "normal_morale_per_turn": 2},
        "morale": {"deck_size": 8, "pay": {"from": "active", "to": "rested"}, "return": {"allowed_states": ["active", "rested"], "destination": "morale_deck", "card_text_overrides": True}},
        "disaster_draft": {"set_id": "s01-disaster-catalogue", "final_disaster_id": "S01-DS10", "bans": ["first_player", "second_player", "first_player"], "public_random_draw": 1, "first_player_draws": 3, "first_player_selects": 1, "second_player_draws": 2, "second_player_selects": 1, "deck_order": "shuffle_selected_then_place_above_final"},
        "training_gate": {"requires_ruleset_status": "verified", "requires_all_referenced_content_implemented": True},
    }
    write_json(RULESETS / "standard-2.0-s01.json", standard)

    historical_source = "规则与卡池/规则手册.pdf"
    historical_path = RULESETS / "handbook-v1-2025-04-26.json"
    existing_pages: dict[str, dict[str, object]] = {}
    if historical_path.exists():
        existing = json.loads(historical_path.read_text(encoding="utf-8"))
        existing_pages = {
            str(item["rule_id"]): item
            for item in existing.get("rules", [])
            if isinstance(item, dict) and isinstance(item.get("rule_id"), str)
        }
    pages = []
    for page in range(1, 23):
        rule_id = f"handbook-v1-2025-04-26-page-{page:03d}"
        record = existing_pages.get(rule_id, {})
        record.update(
            {
                "rule_id": rule_id,
                "title": record.get("title") or f"规则手册 Ver1.0 · 第 {page} 页",
                "chapter_tags": HISTORICAL_PAGE_TAGS[page],
                "implementation_status": "not_started",
                "review": record.get("review")
                or review("Historical handbook requires vision transcription and review; never used by standard-2.0-s01."),
                "source": source(historical_source, page),
            }
        )
        pages.append(record)
    write_json(
        historical_path,
        {
            "schema_version": "1.0",
            "ruleset_id": "handbook-v1-2025-04-26",
            "display_name": "规则手册 Ver1.0（历史参考）",
            "game_version": "S1_legacy",
            "role": "historical_reference_only",
            "must_not_drive": ["standard-2.0-s01", "training", "strict_simulation"],
            "source": {**source(historical_source), "pages": 22},
            "rules": pages,
        },
    )
    write_json(
        RULESETS / "version_differences.json",
        {
            "schema_version": "1.0",
            "comparisons": [
                {
                    "comparison_id": "handbook-v1-vs-standard-2.0",
                    "higher_priority_ruleset_id": "standard-2.0-s01",
                    "lower_priority_ruleset_id": "handbook-v1-2025-04-26",
                    "status": "review_queue",
                    "differences": [
                        {
                            "difference_id": "version-precedence",
                            "status": "verified",
                            "summary": "Ver1.0 is historical reference only and cannot override standard-2.0-s01.",
                        },
                        {
                            "difference_id": "disaster-selection",
                            "status": "needs_review",
                            "historical_reference": "Ver1.0 p.09 and p.15 describe a five-card allocation flow.",
                            "standard_reference": "standard-2.0-s01 stores three bans, one public draw, then 3/2 selections.",
                        },
                        {
                            "difference_id": "reference-decks",
                            "status": "needs_review",
                            "historical_reference": "Ver1.0 p.14 preconstructed lists are retained as historical text only.",
                            "standard_reference": "Two current first-match reference decks live in data/s1/reference_decks.json.",
                        },
                    ],
                    "review_queue": [
                        {"topic": "turn_and_combat_flow", "status": "needs_comparison_review"},
                        {"topic": "deckbuilding_and_faction_rules", "status": "needs_comparison_review"},
                    ],
                }
            ],
        },
    )


def update_sources() -> None:
    path = ROOT / "data/strategy_sources/source_registry.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    extras = [
        {"source_id": "rules-2.0-source-pdf", "title": "规则手册 2.0", "source_type": "official_rules", "local_path": "规则与卡池/规则手册2.0.pdf", "sha256": sha256(PDF_DIR / "规则手册2.0.pdf"), "status": "structured_rule_truth", "use": "standard-2.0-s01 的规则真值，与正式卡面共同优先"},
        {"source_id": "s1-tianting-yang-jian-guide", "title": "S1 天廷阵营构筑见解之 杨戬", "source_type": "official_deck_guide", "local_path": "规则与卡池/S1天廷阵营构筑见解之 杨戬.pdf", "sha256": sha256(PDF_DIR / "S1天廷阵营构筑见解之 杨戬.pdf"), "status": "structured_reference_deck", "use": "杨戬天廷参考构筑与策略先验，不作为胜率证据"},
        {"source_id": "s1-sun-city-mejed-guide", "title": "S1 太阳城阵营构筑见解之 梅杰德", "source_type": "official_deck_guide", "local_path": "规则与卡池/S1太阳城阵营构筑见解之 梅杰德.pdf", "sha256": sha256(PDF_DIR / "S1太阳城阵营构筑见解之 梅杰德.pdf"), "status": "metadata_only", "use": "保留为非首测策略来源，不进入 S1 天廷/高天原模拟"},
        {"source_id": "handbook-v1-2025-04-26", "title": "规则手册 Ver1.0", "source_type": "historical_rulebook", "local_path": "规则与卡池/规则手册.pdf", "sha256": sha256(PDF_DIR / "规则手册.pdf"), "status": "historical_reference_only", "use": "页面转录与版本差异追溯；不得覆盖规则手册 2.0"},
    ]
    by_id = {entry["source_id"]: entry for entry in entries}
    for entry in extras:
        if entry["source_id"] in by_id:
            by_id[entry["source_id"]].update(entry)
        else:
            entries.append(entry)
    write_json(path, entries)


def main() -> int:
    update_catalog()
    write_s1_content()
    write_rulesets()
    update_sources()
    print("seeded S1 structured data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
