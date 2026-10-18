# 录入流程 · 证据、四轨、横向边、技能

> **本文是 `SKILL.md` 的子文档**，装 §6.1–§6.7 的完整规程。
> **何时读**：用户说出「我做过 / 我会 / 我一般是 / 这条不对 / 这两条有关系」，或一次回答结束要落盘。
> **算分公式**在 `model.md` §3；**没有脚本时的手工做法**在 `manual-mode.md` §0.8。
> **读完**：回到 `SKILL.md` §1 场景路由表继续。

---

## 6.1 录入证据

```bash
python3 scripts/ingest.py --user <id> --target <kp_id> \
    --type project_lead --note "主导支付重构"
```

查知识点 id：`grep -rl "name: 性能优化" users/<id>/points/`

**多目标**（一条证据同时点亮多个知识点——共现的唯一来源，见 §6.6）：

```bash
python3 scripts/ingest.py --user <id> --target "消息传递机制" --target "谱图理论" \
    --type artifact --note "复现 GNN 过度平滑时同时用到两者"
```

**技能目标**（分数进 `level` 而不是 `raw_score`，见 §6.7）：

```bash
python3 scripts/ingest.py --user <id> --skill --target "信息检索" --type project_lead
```

**负向证据**（遗忘，走乘系数而不是累加，见 `model.md` §3.2）：

```bash
python3 scripts/ingest.py --user <id> --target "傅里叶变换" --type forgot
```

`--target` 接受 **id / 知识点名 / 文件名主干**三者之一。

> 查不到名字时**不要猜 id**——先用 `query.py` 或 `grep` 确认。
> 模式 A 下若提示「未找到知识点」，说明名字与库里不一致（含错别字、简称），
> 先按别名规则对齐，别新建一条重复的。

## 6.2 B 轨：项目 → Playbook

```
项目 Project      目标、角色、起止、能力标签        ← 必录
  └ 行动 Action   流程、卡点、怎么解的              ← 选录
      └ 产物 Artifact  文档/代码/设计稿/报告/链接     ← 选录
```

**项目层必录，行动与产物选录**，靠对话沉淀补。
强求全量填的表最后都会变成空表。

经验录入后做**反哺映射**：推导用到/印证了哪些知识点 → 生成证据 → 点亮 A 轨。
这一步用 §6.1 的多目标录入完成——项目的 `touched_points` 有几个，就 `--target` 几次。

积累 **2 次以上**同类项目后，提炼 Playbook（适用场景 / 标准流程 / 已知坑位 / 关联知识点）。
下次遇到同类事件，**直接调 Playbook 而非从零推演**——这是"让智能体按用户经验处理同类事件"的实现方式。

预置的 7 个流程模板在 `templates/playbooks.md`（任务拆解与排期 / 优先级判断 / 会议组织 /
文档沉淀 / 复盘方法 / 风险管理 / 求职准备）——**是模板，不是用户的经验**，
只有用户的项目真的跑通了才 `verified_count += 1`。

## 6.3 C 轨：智慧原则

录入时机：从多条经验中归纳出共性时；用户说出"我一般是…"这类原则性表述时。

字段：`statement`（一句话，可迁移）/ `domain`（`*` 通用）/ `confidence` /
`source`（derived / declared）/ `counter`（反例或适用边界）。

`counter` 是必填项而不是选填——没有边界的原则会变成教条，
下次套用时会害人。写不出 `counter` 说明还没到能提炼的时候。

## 6.4 D 轨：行为特征

轻量特征卡，**一条一特征，禁止写成人物传记**。

必须区分 `observed`（你观察到）与 `declared`（用户明说），置信度不同。

**observed 推断后必须轻量告知**：
> 我注意到你更习惯先看例子再看定义，要记下来吗？

用户可否认或修正。**连续观察到 3 次以上**才建议记录，避免把偶然当习惯。

## 6.5 纠错

用户说"这条不对/标错了" → 设 `rejected: true`，不参与计算、不出现在报告中。
**不要删除文件**——保留记录便于日后追溯"为什么这条被排除"。

> 纠错属于**改一条数据**，直接改；用户质疑的是**规则本身**（"凭什么半衰期 90 天"）
> 就属于系统改进，走 `improving.md` §8，不许直接动手。

## 6.6 横向边：知识点 ↔ 知识点

纵向边（域 → 学科 → 课程 → 知识点）来自 `graph/`，是公共的；
**横向边是个人的**，只能长在档案里。它记的是「这两件事你在同一个场景里用过」。

```bash
python3 scripts/link.py --user <id> --suggest        # 找候选（auto 档直接建）
python3 scripts/link.py --user <id> --accept "A" "B" # 同意建议
python3 scripts/link.py --user <id> --reject "A" "B" # 拒绝，此后不再建议
python3 scripts/link.py --user <id> --add "A" "B"    # 用户主动声明
python3 scripts/link.py --user <id> --list
```

三档，**不要越档**：

| 档 | 条件 | 动作 |
|---|---|---|
| `auto` | 同域 **且** 共现 ≥3 次 | 直接建，可撤销 |
| `suggest` | 跨域，或共现 1–2 次 | **先问用户**，同意才建 |
| `manual` | 用户自己说的 | 直接建 |

**建议必须带依据，且只在不打断主线时提**：

> 你在「论文复现：GNN 过度平滑」里同时用到了『消息传递机制』和『谱图理论』，
> 这条线要连上吗？（依据：共现 3 次，ev_a1、ev_b2）

- 单次最多 3 对，一次能答完
- 拒绝过的同一对**永不再问**（写进 `edges.md`）
- 没有依据不许建议——否则你会开始随机连边

落到文件上是三处，各有各的用处：本体在两端 `related: [名字]`（机器读）、
正文 `## 关联` 里是 `[[名字]]`（Obsidian 画图）、`edges.md` 记决策（人查账）。
建边同时写一条 `edge_confirm` 证据（**权重 0**）——确认相关不等于更懂了。

> 正文那块由 `related` 派生，包在 `<!-- related:start -->` / `<!-- related:end -->` 里，
> **不要手改**：下次同步会覆盖。

## 6.7 技能实体：会不会做

```bash
python3 scripts/skill.py --user <id> --seed                  # 铺预置技能簇（level 一律 0）
python3 scripts/skill.py --user <id> --requires "信息检索" --points "信息检索,资料筛选与判别"
python3 scripts/skill.py --user <id> --add "论文复现" --cluster 学术研究 --kind composite
python3 scripts/skill.py --user <id> --list                  # 含 gap
python3 scripts/ingest.py --user <id> --skill --target "信息检索" --type project_lead
```

**两套分数，永不互相推导**：

| | 来源证据 | 字段 | 回答 |
|---|---|---|---|
| 知识点 | `study` / `teaching` / `artifact` | `raw_score` | 懂不懂 |
| 技能 | `project_lead` / `artifact` / `selftest_pass` | `level` | 会不会 |

```
gap = level(技能) − mean(current_score(该技能 requires 的知识点))
```

| gap | 含义 | 你该做什么 |
|---|---|---|
| **> +20** | 手熟，原理淡了（凭手感） | 补原理、给推导 |
| **−20 ~ +20** | 知行相当 | 正常讲 |
| **< −20** | 学过，没实践过（纸上谈兵） | 给练习、少讲理论 |

**为什么值得单独算**：任何简历只能回答「你做过什么」，回答不了
「你手上会的，和你脑子里懂的，是否一致」——而这个错位恰好决定该补课还是该练手。
`requires` 为空的 `tacit` 技能不出 gap，**这是正常状态，不是缺数据**。

**建技能的三个门槛**（不满足就只记经验，不建技能）：

1. 用户是**做**过，不只是**学**过——行为证据，不是学习证据
2. 有个名字能代表这个能力（「信息检索」而不是「用 Google 很溜」）
3. 能说清它**要求哪些知识点**（`tacit` 类除外）

---

落盘完，回到 `SKILL.md` §1；本次会话结束前跑一遍 `improving.md` §10.5 的自检清单。
