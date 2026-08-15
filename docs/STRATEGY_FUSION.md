# 人类强策略融合设计

## 1. 目的

“先融合强策略”并不等于抄一套卡表。我们需要把人类知识拆成可验证的对象：

- 构筑骨架；
- 连动 package；
- 起手换牌规则；
- 资源阈值；
- 典型行动路线；
- 对局特定应对；
- 失败条件与风险；
- 证据质量。

## 2. 来源权重

每个来源的有效权重由以下因素组成：

```text
来源可靠性
× 证据类型系数
× 样本量修正
× 版本匹配
× 对局匹配
```

当前代码实现了可靠性、证据类型、样本量和对局匹配；版本匹配会在卡牌版本字段完整后加入硬过滤。

融合时使用：

```text
0.65 × 加权中位数
+ 0.35 × 加权平均数
```

再根据总证据量向中性先验收缩。这样一个极端攻略不能轻易把策略带偏，而多份一致证据会得到更高置信度。

## 3. 不把互斥流派硬平均

例如高天原的快攻与解场控制属于不同专家：

```text
Takamagahara/AggroMobility
Takamagahara/TacticalControl
```

只有在状态门控或卡组明确为混合构筑时才混合二者。否则把快攻和控制直接平均，往往会得到既不够快、又不够稳的中间策略。

## 4. 行动评分

规则引擎为每个合法行动计算一组状态相关特征：

```text
immediate_win
prevent_immediate_loss
tempo
board_control
card_advantage
morale_waste
combo_progress
disaster_resilience
overextension_risk
information_gain
... faction-specific features
```

融合策略给每个特征一个权重。基础分数为：

\[
S(a\mid s)=\sum_j w_j(s)\,f_j(s,a)
\]

但最终动作不直接由线性分数决定，而是：

```text
安全规则
→ 线性评分筛出前 K 个动作
→ 搜索或 rollout 校正
→ 风险与不确定性惩罚
```

## 5. 行为克隆与强化学习的关系

后期网络不从空白开始：

1. 用人类和搜索日志做行为克隆；
2. 网络学习专家策略的快速近似；
3. 强化学习学习残差：

\[
Q_{final}(s,a)=Q_{expert}(s,a)+\Delta Q_{network}(s,a)
\]

4. 新策略只有在留出对手和实战回放中稳定优于专家基线，才进入策略池。

## 6. 卡组融合

卡组不是按单卡投票，而是按 package 处理：

```json
{
  "package_id": "example_combo",
  "cards": ["card_a", "card_b", "card_c"],
  "minimum_counts": {"card_a": 3, "card_b": 2},
  "role": "primary_win_condition",
  "dependencies": ["draw_engine"],
  "conflicts": ["another_package"]
}
```

搜索优先回答：

- 整个 package 是否值得保留；
- 组件数量是否合理；
- 组件单独抽到时是否仍有用；
- package 对士气曲线和死手率的影响；
- 面对不同天灾是否过于脆弱。

## 7. 防止来源偏差

必须显式处理：

- 只上传获胜局；
- 视频剪掉失误或无聊回合；
- 构筑版本过期；
- 对手水平不一致；
- 只在特定对局有效；
- 单次高上限组合幸存者偏差；
- 玩家操作强，卡组本身未必强。

因此每条策略都保留来源、版本、样本量、对局和置信度；无法确认的信息保持为空，而不是猜测。

## 8. 第一批融合输出

对每个阵营/主宰输出：

- `stable`: 稳健泛用版；
- `high_ceiling`: 高上限组合版；
- `matchup`: 针对指定对手版；
- `policy_prior`: 行动特征权重；
- `mulligan_rules`: 起手规则；
- `packages`: 核心与可替换组件；
- `uncertainties`: 证据不足和争议点。
