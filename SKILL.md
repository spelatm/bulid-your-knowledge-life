---
name: knowledge-profile
description: >
  量化一个人的知识掌握度、实践经验与行为特征，构建可长期累积的个人能力档案，
  并据此决定讲多深、怎么讲、调取哪次经验。三种情况必须触发——
  (1) 会话开始或首次接触：先跑启动协议，必要时采集学历/职业/区域三项背景；
  (2) 用户提出讲解、教学、咨询、复盘、选型、学习计划类问题：先查档案再决定深度；
  (3) 用户说出背景、经历、项目或给出资料链接：抽取知识点与证据写入档案。
  触发词：知识点、掌握度、学科、遗忘、生疏、能力画像、经验库、智慧原则、我的档案、
  我学过、我做过、这个项目、我一般是、帮我补全。
  背景超出静态模板时，必须联网检索该背景的知识体系与能力要求来扩展档案
  （references/expansion.md）。
  不触发：与用户本人能力无关的纯事务请求（写邮件、翻译、算数、查天气、
  纯资讯检索）——直接办，不查档案、不写日志。
version: 3.6.0
tags: [knowledge, profile, expertise, memory, decay, onboarding, self-improving, network-inference, web-expansion, progressive-disclosure, obsidian, taxonomy]
---

# 知识与经验量化系统 · 执行手册（主文档）

> **读者**：执行本 Skill 的智能体。全文的「你」= 你。
> **性质**：操作规程（做什么、按什么顺序做），不是设计说明。命令式条目即为你要执行的动作。
> **定位**：不是资料仓库，而是一个人的**能力数字孪生**——
> 用可审计的证据记录「他知道什么、做过什么、怎么判断、卡在哪」，
> 让他每次得到的回答都贴合他的真实水平，而不是通用答案。

**这是一份索引式主文档。** 本文只装三样东西：**你的角色约束、判断部署形态、按场景路由**。
具体动作怎么做，在 `references/` 下的七份子文档里——**按当前要做的那件事读一份，不要全读**。

| 子文档 | 一句话 | 何时读 |
|---|---|---|
| `references/onboarding.md` | 建档、采集话术、冷启动推断 | 用户刚建档 / 状态 `new` `partial` |
| `references/answering.md` | 提问流程、报告八节、交互规范 | 用户提问 / 要看分布 |
| `references/recording.md` | 证据、四轨录入、横向边、技能 | 要往档案写东西 |
| `references/expansion.md` | 联网扩展档案 | 背景超出静态模板 |
| `references/manual-mode.md` | 没有脚本时的全部做法 | 模式 A−/B |
| `references/model.md` | 算分公式、字段表、配置速查 | 算分 / 改配置 / 查字段 |
| `references/improving.md` | 系统改进五步、脚本清单、自检与反面清单 | 用户提改进 / 收尾自查 |

---

## 读取后立即执行

> 本节在加载后 30 秒内做完，**优先于后文一切内容**。
> 不要等用户开口，不要先读子文档——先做这三件事，再按 §1 查表。

### ① 认领角色：五条不变量

违反任一条即视为执行失败。它们比后文任何细则都优先，任何情况下不得让渡。

| # | 不变量 | 具体含义 |
|---|---|---|
| **I1** | **先查档案，再开口** | 触发本 Skill 后，本会话第一个动作是查档案（`bootstrap` / `query` / 读 `profile.md`），**不是**直接回答。唯一例外：与用户本人能力无关的纯事务请求（§1 第 5 行） |
| **I2** | **无证据不写分** | 分数只能由证据推出。推断必须标 `origin: inferred`，且**不得当作"用户已掌握"来讲** |
| **I3** | **证据只追加** | `evidence/` 永不删除、永不改写。撤销证据 = 追加一条反向证据 |
| **I4** | **改系统先确认** | 涉及规则 / 配置 / 骨架 / 脚本 / **文档结构**的改动，一律走 `improving.md` §8 五步，**绝不先动手** |
| **I5** | **不评判、不夸大** | 不说"你很弱/你忘了"；库里没有就说没有，绝不编造未命中的内容 |

### ② 探测部署形态（决定后面所有命令是否可用）

```bash
ls scripts/bootstrap.py >/dev/null 2>&1 && echo HAS_SCRIPTS || echo NO_SCRIPTS
ls references/onboarding.md >/dev/null 2>&1 && echo HAS_REFS || echo NO_REFS
```

| 形态 | 判断依据 | 工作方式 |
|---|---|---|
| **A · 完整仓库** | `HAS_SCRIPTS` + `HAS_REFS` | 以脚本为准：命令照跑，子文档按路由表读。**`_meta/*.md` 是配置的单一事实源，脚本输出即权威结果**，不要自己另算一套 |
| **A− · 纯文档** | `NO_SCRIPTS` + `HAS_REFS` | 没有脚本：走 `manual-mode.md` §0.8 的**手工口径**自己建档案、自己算分。其余规则完全一致 |
| **B · 单文件** | `NO_REFS` | 连子文档都没有：只按本文末尾的**最小闭环**做，精度略低。**不要凭空发明算法或权重** |

> **A− 与 B 是底线能力，A 只是加速器。**
> A 形态下能做的每件事，在 A−/B 下都必须能靠读写 markdown 完成。
> A 形态但 `python3` 不可用 / 脚本报错 → **降级到 A−**，并把降级事实告知用户一次。

### ③ 跑第一步

- **A**：`python3 scripts/bootstrap.py --check --user <user_id>`
- **A−/B**：手工读 `users/<user_id>/profile.md`，字段齐全即 `ready`，不存在即 `new`

`user_id`：优先用平台已知的稳定标识（用户名 / 账号 ID）；无从判断就用 `default`。
**拿到结果后按它给出的下一步执行，不要自行判断。**

---

## 0. 启动协议（速览）

```
   new ──采集三项背景──▶ partial ──补齐缺项──▶ ready
    │                      ▲                    │
    └──用户说"先跳过"───────┘                    │
                            └──── 后续聊到背景再补 ┘

   ready = 稳态。进入 ready 后：永不再问背景，直接进正常流程。
   partial = 过渡态。只补缺的项，已有的绝不重复问。
```

**三项背景**：学历/专业、职业/年限、生活/工作区域——**一次问清，不要逐项追问**。
完整话术、建档命令、轻量告知口径、不该问的情况、补充咨询 → `onboarding.md`。

---

## 1. 行动手册（按场景查表）

**这是你日常使用最频繁的一节。** 遇到情况先查表，再按动作执行，最后才去读对应子文档。

| # | 触发条件 | 你的动作 | 详见 |
|---|---|---|---|
| 1 | 本次会话的**第一次**响应（无论用户说什么） | 跑一次启动协议；此后本会话不再重复 | `onboarding.md` |
| 2 | 用户回答了背景信息 → 新建档 | 跑 `init_profile.py`，再**批量轻量**告知推断结果 | `onboarding.md` §0.3–0.4 |
| 3 | 静态映射表零命中 / 背景超出映射表覆盖 | **联网检索该背景的知识体系并扩展档案** | `expansion.md` |
| 4 | 用户提出**任何**讲解/教学/咨询/复盘类问题 | 先 `query.py` 查档案，再按深度建议回答 | `answering.md` §5 |
| 5 | 用户问的是与本人能力无关的纯事务（写邮件、翻译、查天气） | **直接办**：不查档案、不写日志 | `answering.md` 节流规则 |
| 6 | 回答结束后 | 写入 E 轨日志；本次暴露遗忘则记负向证据 | `answering.md` §5⑦、`recording.md` |
| 7 | 用户说"我做过 / 我完成了某项目" | 录入 B 轨项目，**反哺点亮 A 轨** | `recording.md` §6.2 |
| 8 | 用户说"我一般是… / 我的原则是…" | 录入 C 轨智慧原则 | `recording.md` §6.3 |
| 9 | 观察到用户稳定习惯（**连续 3 次以上**） | 记 D 轨特征，**并轻量告知** | `recording.md` §6.4 |
| 10 | 用户问"我掌握了什么 / 我的分布" | 跑 `report.py` | `answering.md` §7 |
| 11 | 用户说"这个我忘了 / 想不起来了" | 记负向证据 `forgot`，用中性表述回应 | `model.md` §3.2、`recording.md` §6.1 |
| 12 | 用户说"这条不对 / 标错了" | 标 `rejected: true`，不再参与计算 | `recording.md` §6.5 |
| 13 | 用户**对系统本身**提改进建议 | **验证 → 确认 → 再改**，禁止直接改 | `improving.md` §8 |
| 14 | 距上次 `decay.py` 超过 1 天 | 跑一次衰减，更新状态 | `model.md` §3.3 |
| 15 | 一次回答同时用到了多个知识点 | **一条多目标证据录入**（`--target A --target B`），共现才有燃料 | `recording.md` §6.1、§6.6 |
| 16 | 回答结束、手里有 >0 组共现候选 | 跑 `link.py --suggest`，**最多报 3 对、每对带依据** | `recording.md` §6.6 |
| 17 | 用户说"这两条有关系 / 这两个不是一回事" | `link.py --add` / `--reject`，拒绝的从此不再问 | `recording.md` §6.6 |
| 18 | 用户说"我做过 X / 我会 X"（**做**，不是**学**） | 建/更新技能实体，按行为证据推进 `level` | `recording.md` §6.7 |
| 19 | 技能与它要求的知识点对不上（gap 超 ±20） | 按 gap 方向调整讲法：补原理 / 给练习 | `recording.md` §6.7 |
| 20 | 没有 `scripts/`，或脚本报错要降级 | 改走手工口径，算法不变 | `manual-mode.md` §0.8 |

**优先级铁律**：第 13 项高于一切常规动作——用户要改系统时，
先放下手上的录入和回答，走 `improving.md` §8 完整流程。

---

## 2. 五轨结构（摘要）

```
A 知识图谱 Knowledge     我知道什么          ← 会衰减
B 经验档案 Experience    我做过什么、怎么做    ← 不衰减 → 提炼为 Playbook
C 智慧原则 Wisdom        我怎么判断          ← 几乎不衰减
D 行为画像 Profile       我是什么样的人       ← 缓慢修正
E 问题日志 Questions     我问过什么、卡在哪    ← 零成本自动累积
        ↑
    贯穿五轨的连接器：证据 Evidence（append-only）
```

| 轨 | 回答 | 会过期吗 | 复用方式 |
|---|---|---|---|
| A 知识图谱 | 我知道什么 | **会**，按学科差异化 | 决定讲解深度 |
| B 经验档案 | 我做过什么 | 不会 | 同类事件调 Playbook |
| C 智慧原则 | 我怎么判断 | 几乎不 | 跨领域迁移 |
| D 行为画像 | 我是什么样的人 | 缓慢修正 | 决定表达方式 |
| E 问题日志 | 我问过什么 | — | 知识缺口最诚实的探针 |

**B 轨里有两个实体，别混**：

| | 技能 `experience/skills/` | 经验 `experience/projects\|playbooks/` |
|---|---|---|
| 回答 | 会不会做 | 做过什么、在什么情境下怎么做 |
| 组织轴 | **能力簇** | **情境** |
| 分数 | `level`（行为证据推进，730 天衰减） | 不评分，只记事实 |
| 例子 | 「信息检索」熟练度 53 | 「论文复现：GNN 过度平滑」卡在谱图理论 |

技能是**中转站**：向上连知识点（`requires`），向下连经验（`experience`）。
它是系统里唯一同时连着两侧的节点——所以它不是衍生品，是枢纽。

**三条硬约束**：
- `evidence/` **append-only**。分数是算出来的，不是写死的，任何时刻可审计
- 撤销证据 = 追加反向证据，**禁止删除原记录**
- L0/L1 展示层的数据**必须由 L2 聚合算出**，不得另写一份

> 目录结构、为什么 `skills/` 不在 `graph/` 里、"学科骨架只装能被某门课教的东西"
> 这条纪律 → `manual-mode.md` 的「完整仓库长什么样」一节。

---

## 3. 最小闭环（模式 B：连子文档都没有时）

> **本节是兜底副本，故意与 `model.md` §3 重复**——只有 `SKILL.md` 的人也要能跑起来。
> **模式 A 下不要读本节**，读 `model.md`，并以 `_meta/*.md` 为最终事实源。
> 改公式或档位必须两边同步。

### 算分

```
正向：raw += (100 - raw) × w/100 × confidence        ← 边际递减，0→50 易，80→95 难
负向：raw ×= 系数                                     ← forgot 0.85 / selftest_fail 0.92 / rusty_asked 0.90
衰减：current = raw × 0.5^(距 last_verified_at 天数 / 半衰期)
状态：raw=0 → untouched；1–25 aware；26–50 understood；51–75 applicable；76–100 proficient
      current ≤ peak×0.6 且 peak ≥ 40 → rusty
```

| 证据类型 | w | conf |
|---|---:|---:|
| `project_lead` 主导项目 | 35 | 0.9 |
| `teaching` 教别人/写文章 | 30 | 0.85 |
| `artifact` 有产出 | 25 | 0.85 |
| `selftest_pass` 自测通过 | 20 | 0.8 |
| `user_confirmed` 确认推断 | 12 | 0.7 |
| `study` 系统学习 | 12 | 0.6 |
| `self_report` 自评 | 8 | 0.5 |
| `inferred` 背景推断 | 5 | 0.4 |
| `web_inferred` 联网检索 | 5 | 0.4 |
| `edge_confirm` 连边确认 | **0** | 1.0 |

> 本表是 `_meta/weights.md` 的抄件，**以 `_meta/` 为准**——`ingest.py` 读的是那个文件。

**种子证据**（`role: seed`，冷启动/联网扩展用）：`raw = weight`、**只在 `raw = 0` 时生效**、
置信度固定 1.0。它与累加证据必须分开——不分的话两条 50 分种子会叠成 75，凭空造分。

| 衰减档 | volatile | tooling | foundation | methodology | durable | permanent |
|---|---:|---:|---:|---:|---:|---:|
| 半衰期 | 45 天 | 90 天 | 180 天 | 365 天 | 730 天 | ∞ |
| 适用 | 词汇/API | 工具/框架 | 数理/概念 | 方法论 | **技能** | 母语/常识 |

### 存储（三条最小要求）

1. `users/<id>/points/<知识点名>.md`——**文件名 = 知识点名**，不用 id（要能被 Obsidian 直接读）
2. `users/<id>/evidence/<ev_id>.md`——一条一个文件，append-only，**`target_ids` 写多个值**
3. `users/<id>/profile.md` 与 `edges.md`

**最小字段模板**（字段名必须与模式 A 一致，否则 `bootstrap` 会误判为 `partial`）：

```yaml
# profile.md —— 三项取值出现 "" 未填 未知 - — 之一即视为缺失
education: 计算机本科        # 学历/专业原话
occupation: 前端工程师 5 年   # 职业/年限原话
region: 杭州                # 区域原话
user_id: default
created_at: 2026-10-15
updated_at: 2026-10-15
onboarding: ready           # 三项齐全 = ready，否则 partial
```

```yaml
# points/<知识点名>.md
id: kp_a1b2c3d4
name: 消息传递机制
subject: 计算机科学
course: 图神经网络
domain: 信息与计算技术        # 10 选 1，只作索引，空 = 未归类
importance: 1.0             # 1.0 核心 / 0.6 一般 / 0.3 边缘
profile: foundation         # 衰减档位
prior_exposure: medium      # 先验，永不参与算分
raw_score: 0
current_score: 0
peak_score: 0
last_verified_at: ""
origin: inferred            # preset / inferred / user
rejected: false
evidence_ids: []
status: untouched
related: []                 # 横向边：相关知识点名字，正文 ## 关联 由它派生
```

```yaml
# evidence/<ev_id>.md —— append-only，写完回填 points 的 evidence_ids 与四个分数/状态字段
id: ev_9f8e7d6c
target_type: point          # point / skill / wisdom / feature
target_id: kp_a1b2c3d4      # 主目标（兼容旧脚本）
target_ids: [kp_a1b2c3d4, kp_f9e8d7c6]   # 全部目标：可点亮多个点
type: project_lead
weight: 35
confidence: 0.9
role: ""                    # seed = 冷启动种子分，直接赋值不累加
direction: positive         # positive / negative / neutral
coefficient: ""             # 仅负向时填
occurred_at: 2026-10-15
source_ref: ""              # prj_ / act_ / q_ 或来源 URL
note: 主导支付链路重构
```

**`target_ids` 写多个值是这套系统能长出新东西的唯一入口**：一条证据同时点亮 A 和 B，
就是一次共现；共现够了才谈得上「这两条该连」。只写单值，档案永远是一张平铺的表。

完整字段语义与取值规则在 `model.md` §10.2 / §10.2b；完整手工建库流程（六轨目录、
落盘节奏、手工连边与技能）在 `manual-mode.md` §0.8。
**本节只够跑通「建档 → 提问 → 录入」这一条主线**，其余分支等有了子文档再说。

---

## 4. 反面清单（最常失效的几条）

> 完整版（18 条）在 `improving.md` §10.6。**看到就停手。**

- ❌ **不查档案就开讲** —— 违反 I1，本 Skill 等于没加载
- ❌ **把推断当既成事实讲** —— "你会 React"，实际只是地名推断出来的（违反 I2）
- ❌ **改写或删除 `evidence/` 里的记录** —— 违反 I3，审计链断掉
- ❌ **接到系统改进建议就动手改** —— 必须走 `improving.md` §8 五步（违反 I4）
- ❌ **用评判性措辞描述用户水平** —— "你很弱 / 你忘了"（违反 I5）
- ❌ **逐条追问推断结果** —— 用批量轻量告知，一句话总量 + ≤6 个例子 + 一句纠错邀请
- ❌ **把技能分和知识点分互相换算** —— 一换算 `gap` 恒为 0，这个指标就废了
- ❌ **没有依据就建议连边** —— 依据必须是共现次数 + 触发的证据/项目
- ❌ **为了这套系统拖慢回答** —— 查询/写入失败不阻塞回答
- ❌ **一次把整个 `references/` 全读完** —— 那是把渐进披露又改回单文档

---

## 5. 本文件的自检

改完本文件或任一子文档后，问三个问题：

1. **路由表还指得准吗？** 每个「详见」列的路径都真实存在，且那份子文档里真有这条规矩。
2. **同一个规矩只写在一处吗？** 除了「最小闭环」这个刻意重复的兜底，其余重复都是 bug。
3. **兜底还成立吗？** 假设 `references/` 全被删掉，只按本文能不能跑通建档→提问→录入。

版本变更记录见 `CHANGELOG.md`。改本文属 L4 级改动，走 `improving.md` §8。
