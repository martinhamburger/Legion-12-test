# 十二军团策略实验室（Legion 12 Strategy Lab）

本仓库用于研究《十二军团》的卡组构筑、起手调度、出牌策略、天灾应对与阵营对局。

项目的核心原则不是让强化学习从随机出牌开始摸索，而是：

1. **先融合人类强策略**：官方机制说明、可靠玩家构筑、设计者解说、实战回放和实际对局记录都进入带来源与置信度的策略种子库。
2. **先搜索，后强化学习**：第一版使用专家规则、行动评分、束搜索/蒙特卡洛 rollout 和卡组邻域搜索，尽快得到不笨的基线；强化学习只负责在强基线上继续提升。
3. **先做两个阵营**：仅实现当前要研究的两个阵营和相关卡牌，验证有效后再扩展全部阵营。
4. **每个结论可复现**：固定随机种子、交换先后手、共享随机序列、保存版本与来源，并报告置信区间。
5. **本地优先**：默认在 MacBook Air M5 上运行；云端只作为可选加速器。

> 当前仓库是第一阶段骨架：已经包含策略种子融合、抽牌概率、置信区间与快速实验配置。完整对局引擎需要补充准确的规则版本、卡牌数据和首批真人策略来源。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# 40 张卡组、3 张核心卡、前 6 张至少抽到 1 张的概率
legion12 odds --deck-size 40 --copies 3 --draws 6

# 融合“天廷 / 跳费控制”人类与官方策略种子
legion12 fuse \
  --source data/strategy_sources/s1_official_archetypes.json \
  --faction tianting \
  --archetype ramp_control

pytest
```

## 最快得到有效结果的路径

```text
选择两个阵营
→ 导入规则与卡牌
→ 收集每方 2–5 套可靠人类卡组/对局
→ 构建专家策略种子
→ 只在强卡组附近做受约束搜索
→ 用共同随机数和交换先后手筛选
→ 输出首套卡组、换牌表、出牌优先级和反事实解释
→ 再加入自对弈与强化学习
```

详细方案见：

- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
- [`docs/STRATEGY_FUSION.md`](docs/STRATEGY_FUSION.md)
- [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)

## 目录

```text
configs/                 实验预算与搜索配置
data/strategy_sources/   人类/官方策略来源和结构化先验
src/legion12/deck/       抽牌与卡组概率工具
src/legion12/strategy/   策略来源模型、融合与行动评分
src/legion12/evaluation/ 对局统计、置信区间与早停
src/legion12/engine/     后续加入参考规则引擎
src/legion12/search/     后续加入卡组搜索与局面搜索
web/                     后续加入 GitHub Pages 报告站
```

## 近期实现顺序

1. 锁定实际使用的规则版本和卡牌版本。
2. 选定第一组对抗阵营，只录入这两个阵营会用到的卡。
3. 导入可靠构筑与对局记录，形成可追溯的策略种子。
4. 实现最小可用规则引擎和确定性回放。
5. 建立启发式安全策略、束搜索和 Monte Carlo rollout。
6. 在强构筑附近做受约束卡组搜索，而不是随机生成卡组。
7. 通过 GitHub Pages 输出卡表、费用曲线、胜率、士气浪费和操作建议。

## 版权与数据

仓库默认只保存结构化卡牌字段、统计结果和用户有权使用的素材。公开部署前需要单独确认卡图、完整卡文和视频内容的使用权限。
