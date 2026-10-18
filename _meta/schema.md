# 数据结构定义

> 五轨统一字段规范。所有文件 YAML frontmatter + Markdown 正文。
> **知识点文件名 = 知识点名**（如 `消息传递机制.md`），不用 id——
> 这样档案用 Obsidian 等工具打开时是可直接阅读的，图谱也是中文名。
> id 始终以 frontmatter 的 `id` 字段为准，脚本不依赖文件名。
> 域 / 切面 / 先验的取值规则见 `_meta/domains.md`。

---

## A 轨 · 知识点 `points/*.md`

```yaml
---
id: kp_<8位哈希>
name: 特征值分解
subject: 数学                  # 学科（骨架的一级导航）
course: 线性代数
domain: 自然科学与数学          # 域：10 选 1，只作导航与聚合，**不参与评分**；空 = 未归类
transferable: 0.6             # 切面：可迁移性 0–1（>=0.7 即「通用与跨域方法」视图）
context: [专业]                # 切面：适用语境（专业 / 生活）
prior_exposure: high          # 先验：接触概率 high/medium/low/minimal，**永不参与算分**
stage: 大学                    # 可选
profile: foundation           # 衰减档位
importance: 1.0               # 核心1.0 / 一般0.6 / 边缘0.3，学科聚合加权用
raw_score: 72.0
current_score: 58.3
peak_score: 78.0
status: applicable            # 掌握等级：untouched/aware/understood/applicable/proficient
last_verified_at: 2025-03-11
origin: preset                # preset / inferred / user
rejected: false               # 用户否认的推断项
evidence_ids: [ev_0012, ev_0047]
related: [谱图理论, 消息传递机制]   # 横向边：知识点 ↔ 知识点（写名字，不写 id）
tags: [核心, 考试重点]
---
```

**`related` 为什么写名字而不是 id**：它的用户是**人**——Obsidian 里
`[[谱图理论]]` 要能点得动，图谱要能连得上。id 是给脚本做唯一标识的，
不该出现在链接里。正文里对应有一个由 `link.py` 维护的 `## 关联` 托管块
（`<!-- related:start -->` … `<!-- related:end -->`），两者由同一处生成，
**不要手改托管块里的内容**——下次同步会被覆盖；要改就改 frontmatter 或走脚本。

**三个新字段的性质必须分清**（`domain` / `transferable`+`context` / `prior_exposure`）：

| 字段 | 是什么 | 参与算分 | 参与衰减 |
|---|---|---|---|
| `domain` | 检索与聚合的**索引** | ✗ | ✗ |
| `transferable` / `context` | **切面**（横切属性） | ✗ | ✗ |
| `prior_exposure` | **先验猜测**（用于「待验证清单」） | ✗ | ✗ |
| `raw_score` 等 | 证据得出的**实测掌握度** | ✓ | ✓ |

前三个都是**启发值**——它们决定「怎么展示、先问什么」，
绝不决定「你有多强」。一旦混入算分，等于把公共分类当成了个人证据（违反不变量 I2）。

正文：该知识点的个人化备注、当时怎么理解的、易错点。可为空。

---

## B 轨 · 项目 `experience/projects/*.md`

```yaml
---
id: prj_<8位哈希>
name: 论文复现：GNN 过度平滑
role: 主导                    # 主导 / 参与 / 观察
started_at: 2026-09
ended_at: 2026-10
domains: [信息与计算技术, 自然科学与数学]   # 涉及的域 ← 跨域边的原始信号
context: [专业]                # 切面：专业 / 生活
outcome: 部分                  # 成功 / 部分 / 失败
touched_points: [消息传递机制, 谱图理论]   # ← 边②：点亮哪些知识点（写名字）
skills: [信息检索]                        # ← 边③：动用了哪些技能
playbooks: [复盘方法]
blockers: 谱图理论推导不熟，看不透拉普拉斯矩阵的物理含义
artifacts: [https://github.com/…]
---
```

正文：背景、目标、结果、复盘。

> **`blockers` 比 `outcome` 更有信息量。** 「做成了」只能说明结果，
> 「卡在哪」才能定位到该补的知识点——那才是下一次提问的入口。

### 技能 `experience/skills/*.md`

技能是**独立实体**，不是知识点的另一种写法：知识回答「是什么」，技能回答「会不会做」。

```yaml
---
id: sk_<8位哈希>
name: 信息检索
cluster: 信息处理              # 能力簇（来自 skills/ 预设或用户自建）
kind: composite              # composite 可分解 / tacit 隐性手感
requires: [信息检索, 资料筛选与判别]   # ← 边①：由哪些知识点支撑（写名字）
experience: [论文复现：GNN 过度平滑]  # ← 边③：在哪些项目里用过
level: 53                    # 熟练度，**由行为证据独立推进**
last_used_at: 2026-10-18
profile: durable             # 技能衰减档位（730 天）
evidence_ids: [ev_0021]
---
```

**两套分数，互不推导**：

| | 来源 | 字段 | 回答 |
|---|---|---|---|
| 知识点 | 学习证据（study / teaching / artifact） | `raw_score` | 懂不懂 |
| 技能 | 行为证据（project_lead / artifact / selftest_pass） | `level` | 会不会 |

`gap = level − mean(current_score(requires))`。**不要**用知识点分去推技能分，
也不要用技能分去回填知识点分——两者一旦互相推导，`gap` 这个指标就不存在了。

### 行动 `experience/actions/*.md`
```yaml
---
id: act_<8位哈希>
project_id: prj_xxxx
name: 拆分账务核心
flow: 梳理依赖 → 抽接口 → 灰度切流 → 下线旧逻辑
blocker: 双写一致性
resolution: 最终一致 + 对账补偿
touched_points: [消息传递机制, 谱图理论]   # 现在真的会被写入（3.5.0 起）
---
```

### 产物 `experience/artifacts/*.md`
```yaml
---
id: art_<8位哈希>
name: 重构技术方案
type: 文档            # 文档/代码/设计稿/报告/数据/链接
path_or_url: ...
project_id: prj_xxxx
---
```

### Playbook `experience/playbooks/*.md`
```yaml
---
id: pb_<8位哈希>
name: 遗留系统重构标准流程
applicable_when: 老系统需要重写但业务不能停      # ← 情境，索引键
steps: [先跑通官方代码, 再改超参, 再改结构]
anti_patterns: [一上来就自己重写]              # ← 踩过的坑，最有价值的部分
derived_from: [支付系统重构, 订单中心拆分]        # 从哪几个项目长出来的（写名字）
related_points: [消息传递机制]
verified_count: 3
confidence: 0.85
---
```
正文分四节：适用场景 / 标准流程 / 已知坑位 / 关联知识点。

> `derived_from` 为空 = **这不是经验，是一条通用建议**。
> 没有来源的 Playbook 不该落盘——模板见 `templates/playbooks.md`。

---

## C 轨 · 智慧原则 `wisdom/*.md`

```yaml
---
id: wis_<8位哈希>
statement: 技术选型先看团队熟悉度，再看先进性
domain: 技术管理            # * 表示通用
confidence: 0.8
source: derived             # derived / declared
derived_from: [prj_xxxx, prj_yyyy]
counter: 团队有明确技术升级诉求时不适用
---
```

---

## D 轨 · 行为特征 `features/*.md`

```yaml
---
id: feat_<8位哈希>
feature: 学习习惯-偏好实例驱动
value: 看例子比看定义快
confidence: 0.7
source: observed            # observed / declared
evidence: 近5次提问中4次先要例子
confirmed_by_user: false
---
```

---

## E 轨 · 问题日志 `questions/*.md`

```yaml
---
id: q_<8位哈希>
question: 红黑树和 AVL 树怎么选
touched_points: [kp_0033, kp_0034]
resolved: true
asked_at: 2026-10-14
derived_evidence: [ev_0102]
---
```

---

## 连接器 · 证据 `evidence/*.md`（append-only）

```yaml
---
id: ev_<8位哈希>
target_type: point          # point / skill / wisdom / feature
target_id: kp_0021          # 主目标。保留是为了兼容旧脚本
target_ids: [kp_0021, kp_0088]   # 全部目标：**一条证据可以点亮多个点**
type: project_lead          # 见 weights.md
weight: 35
confidence: 0.9
role: ""                    # seed = 冷启动种子分（直接赋值，不累加）
direction: positive         # positive / negative / neutral
coefficient: ""             # 负向证据时填系数
occurred_at: 2024-09-20
source_ref: prj_xxxx
note: 主导支付重构账务拆分
---
```

**`target_ids` 是横向边的燃料。** 一条证据同时点亮 A 和 B，就是一次「共现」；
共现次数够了，`link.py` 才会建议把它们连起来。只写单值，系统就永远发现不了
「这两件事你是在同一个场景里用到的」——而这正是任何简历都答不出的信息。

**append-only**：证据只追加、不修改、不删除。分数由证据重算得出，任何时刻可审计。
如需撤销，追加一条反向证据，而非删除原记录。

---

## 横向边登记簿 `edges.md`

边**本体**在两个知识点的 `related` 字段里，这个文件只记**决策**（谁、何时、凭什么、
拒过哪对）。拒绝过的对不再被建议。

```markdown
| A | B | 状态 | 来源 | 共现 | 依据 | 时间 |
|---|---|---|---:|---|---|
| 消息传递机制 | 谱图理论 | active | cooccur | 3 | ev_a1, ev_b2 | 2026-10-18 |
| 注意力机制 | 索引与 B+ 树 | rejected | user | 1 | ev_c3 | 2026-10-18 |
```

| 来源 | 含义 |
|---|---|
| `cooccur` | 同域且共现 ≥3 次，自动建立（可撤销） |
| `confirmed` | agent 建议、用户确认 |
| `user` | 用户主动声明 |
| `rejected` / `removed` | 用户拒绝 / 主动撤销 |
