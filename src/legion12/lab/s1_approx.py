"""A transparent, reproducible S1 macro-game learning lab.

This module is deliberately not a Legion 12 rules engine.  It models only a
small teaching environment and exports its approximation boundary with every
result.  Strict S1 loading remains in :mod:`legion12.catalog.s1`.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legion12.evaluation.statistics import MatchSummary
from legion12.strategy.fusion import fuse_strategy, load_strategy_sources
from legion12.strategy.scoring import score_action

LAB_ID = "s1-approx-v0"
DISCLAIMER = "近似规则实验：仅用于学习节奏、资源交换与出牌逻辑，不代表正式规则胜率。"
UNMODELED = ["天灾", "反击响应链", "前后排", "复杂目标选择", "未实现卡文", "隐藏信息博弈"]


@dataclass(frozen=True, slots=True)
class LabConfig:
    seed: int = 20260817
    training_episodes: int = 20_000
    evaluation_games: int = 1_000
    max_turns: int = 10
    epsilon_start: float = 0.30
    epsilon_end: float = 0.04


@dataclass(slots=True)
class Unit:
    card_id: str
    troops: int
    ready_turn: int
    charge: bool


@dataclass(slots=True)
class PlayerState:
    faction: str
    leader_id: str
    health: int
    deck: list[str]
    hand: list[str] = field(default_factory=list)
    board: list[Unit] = field(default_factory=list)
    active_morale: int = 0
    rested_morale: int = 0
    artifact_bonus: int = 0
    hand_draw_bonus: int = 0

    @property
    def morale_total(self) -> int:
        return self.active_morale + self.rested_morale


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _numbers(text: str) -> list[int]:
    return [
        int(value) for value in "".join(char if char.isdigit() else " " for char in text).split()
    ]


def _profile_from_card(card: dict[str, Any]) -> dict[str, Any]:
    text = str(card.get("text") or "")
    tags = set(card.get("tags", []))
    numbers = _numbers(text)
    approximated: list[str] = []
    omitted = list(UNMODELED)
    features: dict[str, float] = {
        "tempo": round((card.get("cost") or 0) / 8, 2),
        "card_advantage": 0.0,
        "morale_acceleration": 0.0,
        "board_control": 0.0,
        "face_pressure": 0.0,
        "defense": 0.0,
        "risk": 0.0,
    }
    if "抽取" in text or "加入手牌" in text:
        features["card_advantage"] += 1.0
        approximated.append("过牌或检索")
    if "追加" in text or "活跃登场" in text:
        features["morale_acceleration"] += 1.0
        approximated.append("追加士气或加速登场")
    if "冲锋" in text:
        features["face_pressure"] += 1.0
        approximated.append("冲锋")
    if "击杀对方" in text:
        features["board_control"] += 1.5
        approximated.append("解场")
    if "兵力+" in text or "强攻" in text:
        features["face_pressure"] += 0.75
        approximated.append("兵力增益或强攻")
    if "抵挡" in text or "挑衅" in text or "无法被" in text:
        features["defense"] += 1.0
        approximated.append("防御")
    if "返还" in text:
        features["risk"] += 0.5
        approximated.append("返还士气")
    troops = int(card.get("stats", {}).get("troops", 0))
    return {
        "profile_id": card["official_card_id"],
        "name": card.get("name", card["official_card_id"]),
        "kind": card.get("engine_card_type"),
        "cost": int(card.get("cost") or 0),
        "troops": troops,
        "health": int(card.get("stats", {}).get("blood", 0)),
        "charge": "冲锋" in text,
        "draw": 1 if "抽取" in text or "加入手牌" in text else 0,
        "morale_gain": 1 if "追加" in text else 0,
        "removal": 1 if "击杀对方" in text else 0,
        "buff": 1000 if "兵力+" in text or "强攻" in text else 0,
        "defense": 1 if "抵挡" in text or "挑衅" in text else 0,
        "return_morale": 1 if "返还" in text else 0,
        "features": features,
        "approximated": approximated or ["基础费用与兵力"],
        "unmodeled": omitted,
        "source_text": text,
        "review_status": card.get("review", {}).get("status", "unknown"),
        "numbers_seen": numbers,
        "tags": sorted(tags),
    }


def build_profiles(root: Path) -> dict[str, Any]:
    """Build profiles for exactly the two first-match decks and resources."""

    pool = _read(root / "data/card_pools/s01/card_pool.json")
    decks = _read(root / "data/s1/reference_decks.json")["decks"]
    by_id = {card.get("official_card_id"): card for card in pool["cards"]}
    selected_ids = sorted({card_id for deck in decks for card_id in deck["cards"]})
    profiles = []
    for card_id in selected_ids:
        card = by_id.get(card_id)
        if card is None:
            raise ValueError(f"reference deck card is missing from card pool: {card_id}")
        profiles.append(_profile_from_card(card))
    leaders = []
    for deck in decks:
        leader = by_id.get(deck["ruler_official_card_id"])
        if leader is None:
            raise ValueError(f"reference deck ruler is missing: {deck['ruler_official_card_id']}")
        leaders.append(_profile_from_card(leader))
    resources = _read(root / "data/s1/faction_resources.json")["factions"]
    resource_profiles = [
        {
            "profile_id": f"resource:{resource['faction_id']}",
            "name": f"{resource['label']}士气资源",
            "kind": "faction_morale",
            "approximated": ["阵营资源的抽牌、追加士气或位移倾向"],
            "unmodeled": list(UNMODELED),
            "source_text": resource["text"],
            "review_status": resource["review"]["status"],
        }
        for resource in resources
    ]
    if len(profiles) != 29 or len(leaders) != 2 or len(resource_profiles) != 2:
        raise ValueError("S1 lab profile coverage is incomplete")
    return {
        "schema_version": "1.0",
        "lab_id": LAB_ID,
        "disclaimer": DISCLAIMER,
        "coverage": {
            "main_cards": len(profiles),
            "leaders": len(leaders),
            "resources": len(resource_profiles),
            "unmodeled": list(UNMODELED),
        },
        "profiles": profiles,
        "leaders": leaders,
        "resources": resource_profiles,
    }


def _expand_deck(deck: dict[str, Any]) -> list[str]:
    return [card_id for card_id, copies in deck["cards"].items() for _ in range(copies)]


def _draw(player: PlayerState, amount: int) -> None:
    for _ in range(amount):
        if player.deck:
            player.hand.append(player.deck.pop())


def _mulligan(player: PlayerState, profiles: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    opening = list(player.hand)
    replace = [card_id for card_id in player.hand if profiles[card_id]["cost"] >= 6]
    for card_id in replace:
        player.hand.remove(card_id)
        player.deck.insert(0, card_id)
    _draw(player, len(replace))
    return {
        "opening": opening,
        "replaced": replace,
        "kept": [card for card in opening if card not in replace],
    }


def _state_key(player: PlayerState, opponent: PlayerState, turn: int) -> str:
    return "|".join(
        str(value)
        for value in (
            player.faction,
            min(turn, 10),
            min(player.health, 10),
            min(opponent.health, 10),
            min(player.active_morale, 8),
            min(len(player.hand), 8),
            min(len(player.board), 3),
            min(len(opponent.board), 3),
        )
    )


def _actions(player: PlayerState, profiles: dict[str, dict[str, Any]]) -> list[str]:
    actions = ["hold"]
    for card_id in sorted(set(player.hand)):
        profile = profiles[card_id]
        if profile["cost"] <= player.active_morale:
            if profile["kind"] == "unit" and len(player.board) >= 3:
                continue
            actions.append(f"play:{card_id}")
    return actions


def _action_features(
    action: str, profile: dict[str, Any] | None, player: PlayerState
) -> dict[str, float]:
    if action == "hold" or profile is None:
        return {"morale_waste": -player.active_morale / 8, "overextension_risk": 0.1}
    values = dict(profile.get("features", {}))
    values["resource_efficiency"] = profile["cost"] / 8
    values["morale_waste"] = -(player.active_morale - profile["cost"]) / 8
    values["overextension_risk"] = -profile.get("return_morale", 0) * 0.4
    return values


def _choose_action(
    policy: str,
    actions: list[str],
    player: PlayerState,
    opponent: PlayerState,
    profiles: dict[str, dict[str, Any]],
    strategy: Any,
    q_table: dict[str, dict[str, float]],
    turn: int,
    rng: random.Random,
    epsilon: float,
) -> tuple[str, str]:
    if policy == "random":
        return rng.choice(actions), "随机合法动作"
    state = _state_key(player, opponent, turn)
    if policy == "learned" and rng.random() >= epsilon:
        values = q_table.get(state, {})
        action = sorted(actions, key=lambda item: (-values.get(item, 0.0), item))[0]
        return action, "Q-learning 估值最高"
    scored = []
    for action in actions:
        card_id = action.split(":", 1)[1] if action.startswith("play:") else None
        profile = profiles.get(card_id) if card_id else None
        scored.append((action, score_action(_action_features(action, profile, player), strategy)))
    action = sorted(scored, key=lambda item: (-item[1], item[0]))[0][0]
    return action, "策略先验评分最高"


def _play(
    player: PlayerState,
    opponent: PlayerState,
    action: str,
    profiles: dict[str, dict[str, Any]],
    turn: int,
) -> str:
    if action == "hold":
        return "保留手牌"
    card_id = action.split(":", 1)[1]
    profile = profiles[card_id]
    if profile["cost"] > player.active_morale:
        raise ValueError(f"insufficient morale for {card_id}")
    if profile["kind"] == "unit" and len(player.board) >= 3:
        raise ValueError(f"battlefield is full for {card_id}")
    player.hand.remove(card_id)
    player.active_morale -= profile["cost"]
    player.rested_morale += profile["cost"]
    if profile["kind"] == "unit":
        player.board.append(
            Unit(card_id, profile["troops"] + profile["buff"], turn, profile["charge"])
        )
    else:
        if profile["removal"] and opponent.board:
            opponent.board.sort(key=lambda unit: (-unit.troops, unit.card_id))
            opponent.board.pop(0)
        if profile["draw"]:
            _draw(player, profile["draw"])
        if profile["morale_gain"] and player.morale_total < 8:
            player.active_morale += 1
        if profile["kind"] == "artifact":
            player.artifact_bonus += profile["buff"] // 1000
    return f"打出 {profile['name']}"


def _attack(player: PlayerState, opponent: PlayerState, turn: int) -> tuple[int, str]:
    damage = 0
    notes = []
    for unit in list(player.board):
        if unit.ready_turn == turn and not unit.charge:
            continue
        if opponent.board:
            target = min(
                opponent.board, key=lambda candidate: (candidate.troops, candidate.card_id)
            )
            if unit.troops >= target.troops:
                opponent.board.remove(target)
                notes.append(f"{unit.card_id} 击破 {target.card_id}")
            else:
                unit.troops -= target.troops
                if unit.troops <= 0:
                    player.board.remove(unit)
        else:
            face = 1 + int(unit.troops >= 6000) + player.artifact_bonus
            opponent.health -= face
            damage += face
            notes.append(f"{unit.card_id} 对主宰造成 {face} 点伤害")
    return damage, "；".join(notes) or "没有可结算的进攻"


def _refresh(player: PlayerState, turn: int, first_turn: bool) -> None:
    player.active_morale += player.rested_morale
    player.rested_morale = 0
    gain = 1 if first_turn else 2
    gain = min(gain, 8 - player.morale_total)
    player.active_morale += max(gain, 0)


def _make_players(
    decks: list[dict[str, Any]], leaders: dict[str, dict[str, Any]], rng: random.Random
) -> list[PlayerState]:
    players = []
    for deck in decks:
        cards = _expand_deck(deck)
        rng.shuffle(cards)
        leader = leaders[deck["ruler_official_card_id"]]
        players.append(
            PlayerState(
                deck["faction_id"],
                deck["ruler_official_card_id"],
                int(leader["health"] or 10),
                cards,
            )
        )
    return players


def _game(
    decks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    leaders: dict[str, dict[str, Any]],
    strategies: dict[str, Any],
    policies: tuple[str, str],
    q_table: dict[str, dict[str, float]],
    seed: int,
    max_turns: int,
    epsilon: float = 0.0,
    trace: bool = False,
) -> dict[str, Any]:
    rng = random.Random(seed)
    players = _make_players(decks, leaders, rng)
    mulligans = {}
    for player in players:
        _draw(player, 6)
        mulligans[player.faction] = _mulligan(player, profiles)
    records: list[tuple[str, str]] = []
    steps: list[dict[str, Any]] = []
    for turn in range(1, max_turns + 1):
        index = (turn - 1) % 2
        player, opponent = players[index], players[1 - index]
        _refresh(player, turn, first_turn=turn == 1 and index == 0)
        if not (turn == 1 and index == 0):
            _draw(player, 1)
        actions = _actions(player, profiles)
        action, reason = _choose_action(
            policies[index],
            actions,
            player,
            opponent,
            profiles,
            strategies[player.faction],
            q_table,
            turn,
            rng,
            epsilon,
        )
        state = _state_key(player, opponent, turn)
        play_note = _play(player, opponent, action, profiles, turn)
        damage, attack_note = _attack(player, opponent, turn)
        records.append((state, action))
        if trace:
            steps.append(
                {
                    "turn": turn,
                    "player": player.faction,
                    "hand": [profiles[card_id]["name"] for card_id in player.hand],
                    "active_morale": player.active_morale,
                    "rested_morale": player.rested_morale,
                    "board": [profiles[unit.card_id]["name"] for unit in player.board],
                    "opponent_health": opponent.health,
                    "legal_actions": actions,
                    "chosen_action": action,
                    "reason": reason,
                    "resolution": f"{play_note}；{attack_note}",
                    "damage": damage,
                }
            )
        if opponent.health <= 0:
            return {
                "winner": player.faction,
                "turns": turn,
                "records": records,
                "steps": steps,
                "mulligans": mulligans,
            }
    winner = max(players, key=lambda item: (item.health, len(item.board), len(item.hand))).faction
    return {
        "winner": winner,
        "turns": max_turns,
        "records": records,
        "steps": steps,
        "mulligans": mulligans,
    }


def _evaluate(
    decks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    leaders: dict[str, dict[str, Any]],
    strategies: dict[str, Any],
    q_table: dict[str, dict[str, float]],
    config: LabConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    wins = Counter()
    games_by_winner = Counter()
    play_counts: Counter[str] = Counter()
    played_games: Counter[str] = Counter()
    conditional_wins: Counter[str] = Counter()
    opening_counts: Counter[str] = Counter()
    kept_counts: Counter[str] = Counter()
    morale_left = 0
    action_turns = 0
    replay_candidates = []
    for game_index in range(config.evaluation_games):
        first = game_index % 2
        ordered = [decks[first], decks[1 - first]]
        game = _game(
            ordered,
            profiles,
            leaders,
            strategies,
            ("learned", "baseline"),
            q_table,
            config.seed + 100_000 + game_index,
            config.max_turns,
            trace=True,
        )
        winner = game["winner"]
        games_by_winner[winner] += 1
        if winner == ordered[0]["faction_id"]:
            wins["learned"] += 1
        played_by_player: set[tuple[str, str]] = set()
        for mulligan in game["mulligans"].values():
            opening_counts.update(mulligan["opening"])
            kept_counts.update(mulligan["kept"])
        for step in game["steps"]:
            morale_left += step["active_morale"]
            action_turns += 1
            if step["chosen_action"].startswith("play:"):
                card_id = step["chosen_action"].split(":", 1)[1]
                play_counts[card_id] += 1
                played_by_player.add((step["player"], card_id))
        for faction, card_id in played_by_player:
            played_games[card_id] += 1
            if game["winner"] == faction:
                conditional_wins[card_id] += 1
        if game_index < 6:
            replay_candidates.append({"seed": config.seed + 100_000 + game_index, **game})
    summary = MatchSummary(wins["learned"], 0, config.evaluation_games - wins["learned"])
    lower, upper = summary.confidence_interval()
    return (
        {
            "games": summary.games,
            "learned_wins": summary.wins,
            "baseline_wins": summary.losses,
            "learned_score": round(summary.score, 4),
            "confidence_95": [round(lower, 4), round(upper, 4)],
            "by_faction": dict(games_by_winner),
        },
        replay_candidates,
        {
            "play_counts": play_counts,
            "played_games": played_games,
            "conditional_wins": conditional_wins,
            "opening_counts": opening_counts,
            "kept_counts": kept_counts,
            "morale_waste_per_turn": round(morale_left / max(action_turns, 1), 3),
            "action_turns": action_turns,
        },
    )


def run_experiment(root: Path, config: LabConfig | None = None) -> dict[str, Any]:
    """Train a small tabular policy and return serialisable teaching artifacts."""

    config = config or LabConfig()
    profile_document = build_profiles(root)
    profiles = {profile["profile_id"]: profile for profile in profile_document["profiles"]}
    leaders = {profile["profile_id"]: profile for profile in profile_document["leaders"]}
    decks = _read(root / "data/s1/reference_decks.json")["decks"]
    sources = load_strategy_sources(root / "data/strategy_sources/s1_official_archetypes.json")
    strategies = {
        "tianting": fuse_strategy(sources, faction="tianting", archetype="ramp_control"),
        "takamagahara": fuse_strategy(sources, faction="takamagahara", archetype="aggro_mobility"),
    }
    q_table: dict[str, dict[str, float]] = defaultdict(dict)
    curve = []
    interval = max(config.training_episodes // 20, 1)
    interval_rewards: list[float] = []
    interval_turns: list[int] = []
    for episode in range(config.training_episodes):
        progress = episode / max(config.training_episodes - 1, 1)
        epsilon = config.epsilon_start + (config.epsilon_end - config.epsilon_start) * progress
        game = _game(
            decks,
            profiles,
            leaders,
            strategies,
            ("learned", "learned"),
            q_table,
            config.seed + episode,
            config.max_turns,
            epsilon=epsilon,
        )
        for state, action in game["records"]:
            faction = state.split("|", 1)[0]
            reward = 1.0 if faction == game["winner"] else -1.0
            old = q_table[state].get(action, 0.0)
            q_table[state][action] = round(old + 0.10 * (reward - old), 6)
        episode_reward = 1.0 if game["winner"] == decks[0]["faction_id"] else -1.0
        interval_rewards.append(episode_reward)
        interval_turns.append(game["turns"])
        if (episode + 1) % interval == 0:
            curve.append(
                {
                    "episode": episode + 1,
                    "epsilon": round(epsilon, 4),
                    "mean_reward": round(sum(interval_rewards) / len(interval_rewards), 4),
                    "win_rate": round(
                        sum(reward > 0 for reward in interval_rewards) / len(interval_rewards), 4
                    ),
                    "mean_turns": round(sum(interval_turns) / len(interval_turns), 3),
                    "mean_q": round(
                        sum(value for actions in q_table.values() for value in actions.values())
                        / max(sum(len(actions) for actions in q_table.values()), 1),
                        4,
                    ),
                }
            )
            interval_rewards = []
            interval_turns = []
    evaluation, replays, analytics = _evaluate(
        decks, profiles, leaders, strategies, q_table, config
    )
    insights = []
    for card_id, profile in sorted(profiles.items()):
        insights.append(
            {
                "card_id": card_id,
                "name": profile["name"],
                "cost": profile["cost"],
                "play_count": analytics["play_counts"][card_id],
                "play_rate": round(analytics["play_counts"][card_id] / config.evaluation_games, 4),
                "mulligan_retention_rate": round(
                    analytics["kept_counts"][card_id]
                    / max(analytics["opening_counts"][card_id], 1),
                    4,
                ),
                "conditional_win_rate": round(
                    analytics["conditional_wins"][card_id]
                    / max(analytics["played_games"][card_id], 1),
                    4,
                ),
                "review_status": profile["review_status"],
                "features": profile["features"],
                "approximated": profile["approximated"],
                "unmodeled": profile["unmodeled"],
            }
        )
    return {
        "schema_version": "1.0",
        "lab_id": LAB_ID,
        "disclaimer": DISCLAIMER,
        "config": {
            "seed": config.seed,
            "training_episodes": config.training_episodes,
            "evaluation_games": config.evaluation_games,
            "max_turns": config.max_turns,
        },
        "coverage": profile_document["coverage"],
        "profiles": profile_document,
        "training_curve": curve,
        "evaluation": evaluation,
        "deck_insights": {
            "cost_curve": dict(
                sorted(
                    Counter(
                        profile["cost"]
                        for deck in decks
                        for card_id, copies in deck["cards"].items()
                        for profile in [profiles[card_id]]
                        for _ in range(copies)
                    ).items()
                )
            ),
            "morale_waste_per_turn": analytics["morale_waste_per_turn"],
            "metric_note": "卡牌条件胜率与打出率均为近似对局相关性，不是因果或强度结论。",
        },
        "card_insights": insights,
        "representative_replays": replays,
        "strict_boundary": "This artifact is not accepted by load_simulatable_reference_decks and never changes strict ruleset status.",
    }
