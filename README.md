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

## 卡池审校站

`规则与卡池/` 的截图式 PDF 可导入为“待复核”卡池：

```bash
python tools/build_card_catalog.py
python tools/build_review_site.py
open build/review-site/index.html
```

首条命令只生成候选数据，不会把 OCR 当作可训练规则；第二条从原 PDF
临时生成 WebP 预览，供 GitHub Pages 或本地浏览器审校。正式数据、原图
来源和训练门禁说明见 [`data/card_pools/s01/README.md`](data/card_pools/s01/README.md)。

### Kimi 视觉预填

将 `.env.kimi.example` 复制为 `.env.kimi` 并在本机填入 Kimi key 后，先用
小样本确认输出，再运行全量预填：

```bash
cp .env.kimi.example .env.kimi
python tools/build_review_site.py
python tools/enrich_card_catalog_kimi.py --limit 3
python tools/enrich_card_catalog_kimi.py
```

该工具只初填候选字段，并始终保留 `needs_review`；它不会上传 key、不会提交
`.env.kimi`，也不会把模型输出直接视为可训练规则。

## S1 近似对局学习实验室

实验室固定使用杨戬天廷与须佐之男高天原的两套 40 张参考构筑，输出可复现的
Q-learning 对规则基线结果、卡牌近似覆盖和逐回合回放：

```bash
python tools/run_s1_approx_lab.py
# 或使用已安装的命令行入口
legion12 lab --seed 20260817 --episodes 20000 --games 1000
python tools/build_review_site.py
```

结果位于 `data/labs/s1-approx-v0/`，Pages 的“学习实验室”页会读取最新结果。
它明确是**近似规则实验**：不模拟天灾、反击响应链、前后排、复杂目标选择及未实现
卡文，不能作为正式对局胜率或严格训练入口。

## 版权与数据

仓库默认只保存结构化卡牌字段、统计结果和用户有权使用的素材。公开部署前需要单独确认卡图、完整卡文和视频内容的使用权限。
