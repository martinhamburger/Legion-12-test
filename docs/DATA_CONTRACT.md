# 数据契约

所有规则、卡牌、卡组、策略来源和对局日志都必须版本化。以下是建议的最小字段。

## 1. 卡牌

```json
{
  "card_id": "S1-TT-001",
  "name": "占位示例",
  "game_version": "S1.0",
  "faction": "tianting",
  "card_type": "unit",
  "cost": 3,
  "copies_max": 3,
  "tags": ["draw", "morale"],
  "roles": ["engine", "curve_filler"],
  "effect": {
    "dsl_version": "0.1",
    "operations": []
  },
  "source": {
    "kind": "user_verified_card",
    "reference": "local-card-scan-or-rulebook-page"
  }
}
```

要求：

- `card_id` 跨版本稳定；
- 修改后的卡文通过 `game_version` 区分；
- 不允许只有自然语言而没有可执行效果；
- 未实现效果必须显式标记，不能静默跳过。

## 2. 卡组

```json
{
  "deck_id": "human-seed-001",
  "name": "示例人类种子卡组",
  "game_version": "S1.0",
  "faction": "tianting",
  "leader": "leader-id",
  "cards": {"S1-TT-001": 3},
  "packages": ["ramp-core"],
  "locked_cards": ["S1-TT-001"],
  "flex_slots": 8,
  "source_ids": ["source-001"],
  "confidence": 0.8
}
```

## 3. 策略来源

```json
{
  "source_id": "source-001",
  "evidence_type": "expert_replay",
  "author": "player-or-channel",
  "url": "https://example.com",
  "published_at": "2026-01-01",
  "game_version": "S1.0",
  "faction": "tianting",
  "archetype": "ramp_control",
  "matchup": "takamagahara",
  "sample_size": 20,
  "reliability": 0.85,
  "feature_weights": {},
  "rules": [],
  "notes": ""
}
```

## 4. 对局日志

```json
{
  "match_id": "match-001",
  "game_version": "S1.0",
  "seed": 12345,
  "first_player": "A",
  "disaster_seed": 67890,
  "decks": {"A": "deck-a", "B": "deck-b"},
  "steps": [
    {
      "step": 0,
      "player": "A",
      "public_state": {},
      "private_observation": {},
      "legal_actions": [],
      "chosen_action": {},
      "source": "human"
    }
  ],
  "result": {"winner": "A", "reason": "normal"}
}
```

保存真人日志时，对手隐藏信息只记录赛后已知真值；训练策略的观察值必须严格使用当时可见信息。

## 5. 实验结果

```json
{
  "experiment_id": "exp-001",
  "engine_commit": "git-sha",
  "rules_version": "S1.0",
  "config": "configs/experiments/quick.json",
  "candidate_deck": "deck-candidate",
  "opponent_population": ["deck-a", "deck-b"],
  "games": 10000,
  "wins": 5300,
  "draws": 100,
  "losses": 4600,
  "metrics": {
    "morale_waste_mean": 0.42,
    "dead_hand_rate": 0.08
  },
  "artifacts": {
    "representative_replays": []
  }
}
```

## 6. 版本门禁

任何实验启动前检查：

- 卡牌版本是否一致；
- 规则版本是否一致；
- 卡组是否合法；
- 所有效果是否已实现或明确近似；
- 对局日志是否包含可复现种子；
- 策略来源是否标注版本与可靠性。
