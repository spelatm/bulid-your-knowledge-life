# 量化模型 · 字段表 · 配置速查

> **本文是 `SKILL.md` 的子文档**，装 §3、§10.2、§10.2b、§10.3 的完整内容。
> **何时读**：要算分 / 要判断状态 / 要改权重或半衰期 / 要确认某个字段叫什么。
> **改这里风险最高**，动手前必走 `improving.md` §8 五步。
> **读完**：回到 `SKILL.md` §1 场景路由表继续。

---

## 3. 量化模型（改这里风险最高）

> 本节表格即配置本身。**模式 A 下若与 `_meta/*.md` 冲突，以 `_meta/` 为准。**

### 3.1 正向证据累积

```
raw_score += (100 - raw_score) × (w / 100) × confidence
```

边际递减：0→50 容易，80→95 极难。

| 证据类型 | w | confidence | 说明 |
|---|---:|---:|---|
| `project_lead` 主导项目实战 | 35 | 0.9 | 最强证据 |
| `teaching` 输出型（教别人/写文章） | 30 | 0.85 | 费曼效应 |
| `artifact` 有产出佐证 | 25 | 0.85 | 有实物强于口头 |
| `selftest_pass` 通过自测 | 20 | 0.8 | — |
| `user_confirmed` 用户确认的推断 | 12 | 0.7 | 推断经确认后升级 |
| `study` 系统学习 | 12 | 0.6 | 输入型不算真掌握 |
| `self_report` 用户自评 | 8 | 0.5 | 冷启动铺底 |
| `inferred` 背景推断（未确认） | 5 | 0.4 | 覆盖广精度低，**不得污染真实分数** |
| `web_inferred` 联网检索（未确认） | 5 | 0.4 | 同 inferred，须附来源 URL |
| `edge_confirm` 关联确认 | **0** | 1.0 | 只留痕、不计分：连上两条 ≠ 你更懂了 |

> 本表是 `_meta/weights.md` 的抄件，**以 `_meta/` 为准**——`ingest.py` 实际读的是那个文件，
> 两边不一致时你是错的。2026-10-18 就抓到过一次：本表曾有 5 行与 `_meta/` 不符
> （`teaching`/`artifact` 的 conf、`user_confirmed`、`study`、`web_inferred`），
> 手工口径按错表算会系统性偏高。

**种子证据是另一条路**（`role: seed`，冷启动与联网扩展用）：
`raw = weight`、只在 `raw = 0` 时生效、置信度固定 1.0。种子分表见 `_meta/weights.md`。
它与上面的累加证据**必须分开**——不分的话，两条 50 分种子会叠加成 75，凭空造分。

**同一知识点证据超过 5 条后，新增权重按 `1/n` 递减**，防刷分。

### 3.2 负向证据（遗忘证据）

| 事件 | 系数 |
|---|---:|
| `forgot` 本该会却没想起来 / 明说忘了 | ×0.85 |
| `selftest_fail` 自测失败 | ×0.92 |
| `rusty_asked` 标记 rusty 且要求从头讲 | ×0.90 |

`raw_score` 因此是**证据净值**，可升可降。这是"记录真实智慧"的前提——
智慧不是只增不减的，遗忘也是真实发生的一部分。

### 3.3 时间衰减

```
current_score = raw_score × 0.5^(Δt / half_life)
```

| 档位 | 半衰期 | 适用 |
|---|---:|---|
| `volatile` | 45 天 | 词汇、API 细节、版本号 |
| `tooling` | 90 天 | 工具、框架、软件操作 |
| `foundation` | 180 天 | 数理基础、核心概念 |
| `methodology` | 365 天 | 方法论、思维模型 |
| `durable` | 730 天 | **技能**（会生疏，不会忘掉「会」） |
| `permanent` | ∞ | 母语、常识 |

每日执行：`python3 scripts/decay.py --user <id> --apply`

### 3.4 状态判定

```
raw = 0                          → untouched  未触及
current 1–25                     → aware      听说过
current 26–50                    → understood 理解原理
current 51–75                    → applicable 能上手做
current 76–100                   → proficient 精通
current ≤ peak×0.6 且 peak ≥ 40   → rusty      生疏了
```

**`rusty` 是全系统最有价值的状态位**——标记的不是"不会"，而是
"曾经会、现在可能废了"。用户卡住时最难受的往往不是不会，
而是"我明明学过，怎么想不起来"；能点破这一点，价值远超讲解本身。

### 3.5 分层暴露

| 层 | 给谁 | 内容 |
|---|---|---|
| L0 概览 | 用户 | 一句话或一张图 |
| L1 档案 | 用户 | 卡片级：等级、上次接触、证据摘要 |
| L2 证据流 | 机器 | 每条证据的类型、权重、时间、置信度 |
| L3 关系网 | 机器 | 知识点依赖、经验→知识点映射、智慧溯源 |

**底层存连续分，展示时才折算等级。** 用户不需要看到 0–100 的数字，
只需知道"掌握到什么程度"。

---

## 10.2 知识点字段

| 字段 | 必填 | 说明 |
|---|---|---|
| id / name / subject / course | ✅ | 标识与归属 |
| raw_score | ✅ | 证据净值，可升可降 |
| current_score | ✅ | 当前鲜活度 = raw × 衰减 |
| peak_score | ✅ | 历史最高，用于判定 rusty |
| last_verified_at | ✅ | 最后验证时间 |
| profile | ✅ | 衰减档位 |
| importance | ✅ | 1.0 核心 / 0.6 一般 / 0.3 边缘，聚合加权用 |
| origin | ✅ | preset / inferred / user |
| evidence_ids | ✅ | 支撑分数的证据 |
| rejected | ⬜ | 用户否认的推断项 |
| status | ✅ | 掌握等级：untouched / aware / understood / applicable / proficient |
| domain | ⬜ | 域（10 选 1，索引；空 = 未归类）——**不参与算分** |
| transferable | ⬜ | 切面：可迁移性 0–1，`>=0.7` 即「通用与跨域方法」视图 |
| context | ⬜ | 切面：适用语境（专业 / 生活） |
| prior_exposure | ⬜ | 先验接触概率 high/medium/low/minimal，**永不参与算分** |
| related | ⬜ | 横向边：相关知识点**名字**（正文 `## 关联` 由它派生） |

> 末四行的字段都是**启发值或关系**：决定「怎么展示、先问什么、连到哪儿」，
> 不决定「你有多强」。取值规则全部在 `_meta/domains.md`——改数值不改代码。

完整字段定义见 `_meta/schema.md`，录入模板见 `templates/README.md`。

## 10.2b 技能实体字段 `experience/skills/`

| 字段 | 必填 | 说明 |
|---|---|---|
| id / name | ✅ | 标识 |
| cluster | ✅ | 能力簇（人际沟通 / 信息处理 / 工具与平台 / 职业素养 / 自建） |
| kind | ✅ | `composite` 可分解 / `tacit` 隐性手感（`tacit` 的 `requires` 可空） |
| requires | ⬜ | 支撑它的知识点**名字**（边① 技能→知识） |
| experience | ⬜ | 在哪些项目里用过（边③ 技能→经验） |
| level | ✅ | 熟练度 0–100，**只由行为证据推进** |
| last_used_at | ⬜ | 最后使用时间（`durable` 档衰减起点） |
| profile | ✅ | 固定 `durable`（730 天） |
| evidence_ids | ✅ | 支撑熟练度的证据 |

---

## 10.3 配置改动速查

| 想调整 | 改哪个文件 | 本文档对应节 |
|---|---|---|
| 各类证据的权重 | `_meta/weights.md` | §3.1 |
| 半衰期与学科档位 | `_meta/decay_profiles.md` | §3.3 |
| 等级区间与展示口径 | `_meta/levels.md` | §3.4 |
| 预置学科骨架（**只装能被课教的**） | `graph/*.md` | `onboarding.md` §4 |
| 预置技能簇（按能力簇，不按学科） | `skills/*.md` | `recording.md` §6.7 |
| 流程类 Playbook 模板 | `templates/playbooks.md` | `recording.md` §6.2 |
| 域 / 切面 / 先验的匹配规则 | `_meta/domains.md` | §10.2 |
| 背景推断规则 | `inference/*.md` | `onboarding.md` §4 |

---

改完任何一条，都要在测试用户上跑一遍 `report.py` 对比前后——
**改配置的代价往往不在数值本身，而在它让哪几条旧数据的等级变了。**
