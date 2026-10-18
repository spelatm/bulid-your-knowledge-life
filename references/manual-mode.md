# 手工口径（模式 B：没有脚本时怎么做）

> **本文是 `SKILL.md` 的子文档**，装 §0.8 与 §10.4 的完整规程。
> **何时读**：`ls scripts/bootstrap.py` 失败（纯 markdown 部署），
> 或模式 A 下 `python3` 不可用 / 脚本报错需要降级。
> **读完**：回到 `SKILL.md` §1 场景路由表继续。

---

## 0.8 手工口径（模式 B：没有脚本时怎么做）

> 没有 `scripts/`、`graph/`、`_meta/` 时，**本节的规则取代前面所有 bash 命令**。
> 你要扮演脚本：自己建目录、自己算分、自己写文件。**算法与模式 A 完全同一套**（`model.md` §3）。

**① 目录结构**（缺失就建，路径均相对本 Skill 根目录）

```
users/<user_id>/
├─ profile.md          档案头（见 ②）
├─ points/             一个知识点一个 .md，**文件名 = 知识点名**（可读，见 ③）
├─ evidence/           append-only 证据，一条一个 .md
├─ questions/          问题日志
├─ experience/projects|actions|artifacts|playbooks|skills/
├─ wisdom/  features/   （用到再建）
├─ edges.md            横向边登记簿（只记决策：谁、何时、拒过哪对）
└─ reports/             report --save 时才产生
```

**② `profile.md`**——**字段名必须与模式 A 一致**，否则 `bootstrap.py` 会误判为 `partial`：

```yaml
---
education: 计算机本科        # 学历/专业原话（字段名固定为 education）
occupation: 前端工程师 5 年   # 职业/年限原话（字段名固定为 occupation）
region: 杭州                # 区域原话
user_id: default
created_at: 2026-10-15
updated_at: 2026-10-15
onboarding: ready           # 三项齐全 = ready，否则 partial（字段名固定为 onboarding）
---

# default 的能力档案

- 学历：计算机本科
- 职业：前端工程师 5 年
- 区域：杭州
```

> 三项取值出现 `""` `未填` `未知` `-` `—` 之一即视为缺失（模式 A 的判定口径）。

**③ `points/<知识点名>.md`**——**文件名就是知识点名**（如 `消息传递机制.md`），
不要用 id。理由：档案应当能用 Obsidian 之类的工具**直接打开阅读**，
哈希文件名在那一侧是一堆乱码。`id` 仍以 frontmatter 的 `id` 字段为准，脚本不依赖文件名。
（名称里的 `/ : * ? " < > |` 换成全角；跨学科重名加「（学科）」后缀。）

```yaml
---
id: kp_a1b2c3d4
name: 消息传递机制
subject: 计算机科学        # 学科，自己归纳，粒度保持稳定
course: 图神经网络         # 课程/方向
domain: 信息与计算技术      # 域：10 选 1，只作索引；空 = 未归类（见 _meta/domains.md）
transferable: 0.5         # 切面：可迁移性 0–1，>=0.7 即「通用与跨域方法」视图
context: [专业]            # 切面：适用语境（专业 / 生活）
importance: 1.0           # 1.0 核心 / 0.6 一般 / 0.3 边缘
profile: foundation       # 衰减档位，见 `model.md` §3.3
prior_exposure: medium    # 先验接触概率，**永不参与算分**，只用于「待验证清单」
raw_score: 0
current_score: 0
peak_score: 0
last_verified_at: ""      # 无证据时留空，有证据时填发生日期
origin: inferred          # preset / inferred / user
rejected: false
evidence_ids: []          # 支撑它的证据 id
status: aware             # 按 `model.md` §3.4 算出的状态名
tags: []                  # 可放强度标签，如 [strong, 网络检索]
---

# 消息传递机制

## 我的理解

## 易错点 / 卡点
```

**④ `evidence/<id>.md`**（append-only，一条一个文件；`id` 形如 `ev_9f8e7d6c`）

```yaml
---
id: ev_9f8e7d6c
target_type: point        # point / skill / wisdom / feature
target_id: kp_a1b2c3d4    # 主目标（兼容旧脚本）
target_ids: [kp_a1b2c3d4, kp_f9e8d7c6]   # 全部目标：**可点亮多个点**
type: project_lead        # 见 `model.md` §3.1 / §3.2
weight: 35                # 正向取 w；负向可留空
confidence: 0.9
role: ""                  # seed = 冷启动种子分（直接赋值，不累加）
direction: positive       # positive / negative / neutral
coefficient:              # 负向时填，如 0.85
occurred_at: 2026-10-15
source_ref:               # 关联的 prj_ / act_ / q_，或联网来源 URL
note: 主导支付链路重构
---
```

写完证据后，**回填** `points/<id>.md` 的 `evidence_ids`、`raw_score`、
`current_score`、`peak_score`、`status`、`last_verified_at`——两处必须一致。

> **`target_ids` 写多个值，是这条系统能长出新东西的唯一入口。**
> 一条证据同时点亮 A 和 B，就是一次共现；共现够了才谈得上「这两条该连」。
> 只写单值，档案永远只是一张平铺的表。

**⑤ 算分（照 `model.md` §3 的公式手工推算，别估算）**

```
正向：raw += (100 - raw) × w/100 × confidence      ← §3.1 取 w 与 confidence
负向：raw ×= 系数                                   ← §3.2
衰减：current = raw × 0.5^(距 last_verified_at 天数 / 半衰期)   ← §3.3
状态：按 §3.4 判；raw 变了就同步更新 peak_score
```

**算例**：某知识点 `raw=0`，用户主导过一次相关项目（`project_lead`，w=35，conf=0.9）
→ `raw = 0 + (100-0) × 0.35 × 0.9 = 31.5` → 状态 `understood`（26–50），`peak=31.5`。

**⑥ 落盘节奏（重要，避免打断对话）**

- **一次对话结束前批量落盘**，不要每说一句就写文件
- 同一会话内**同一知识点只记一条证据**，合并成更完整的 note
- 写文件失败 → 告知用户一次，继续正常回答，不要卡住

**⑦ 横向边（手工版，对应 `recording.md` §6.6）**

1. 扫 `evidence/`，看哪些证据的 `target_ids` 同时含两个知识点 → 记一次共现
2. 同一对达到 3 次且**同域** → 可直接连；否则**先问用户**，一次最多问 3 对
3. 连的方式：两边 `points/*.md` 的 `related: [名字]` 各加一条，
   正文追加 `## 关联` 与 `- [[对方名字]]`（Obsidian 靠这个画边）
4. 用户拒绝 → 记进 `edges.md`，**同一对不再建议**

**⑧ 技能（手工版，对应 `recording.md` §6.7）**

技能放 `experience/skills/`，**分数（`level`）只来自行为证据**（做过 / 教过别人 / 有产物），
不从知识点分推导。字段：`name` / `cluster` / `kind`(composite|tacit) / `requires`(知识点名) /
`experience`(项目名) / `level` / `last_used_at` / `profile: durable` / `evidence_ids`。

`gap = level − requires 里知识点的 current 均值`：> +20 补原理，< −20 给练习。

---

## 完整仓库长什么样（模式 A，供对照）

```
knowledge-profile/
├─ SKILL.md              主文档：角色 / 不变量 / 模式探测 / 场景路由表
├─ references/           子文档：按会话阶段拆，用到才读（见 SKILL.md 索引）
├─ CHANGELOG.md          系统变更记录（改进必写）
├─ _meta/                配置层：改这里，不改代码
├─ graph/                预置学科骨架（**只装能被某门课教的东西**）
├─ skills/               预置技能簇（按能力簇组织，**不按学科**）
├─ inference/            背景推断模板
├─ templates/            各轨录入模板（含 playbooks.md 流程模板）
├─ scripts/              可执行脚本（模式 A 才有）
├─ design/               设计草案与迁移记录
├─ archive/              仅存 git 无法表达的资产（用户数据快照等）
└─ users/<user_id>/      每用户隔离
   ├─ profile.md
   ├─ edges.md           横向边登记簿（决策与拒绝清单）
   └─ points|experience|wisdom|features|questions|reports|evidence
      └ experience/skills/   技能实体（B 轨）
```

**为什么 `skills/` 不在 `graph/` 里**：`graph/` 是**学科**骨架，第一条纪律是
「装得进某门课」。技能装不进去——「复盘方法」属于哪个学科？没有答案。
把它塞进学科的代价是整个骨架失去可比性（3.4.0 之前 `graph/职业技能.md`
就是这么错的，3.5.0 拆掉，见 `design/职业技能分流-mapping.md`）。

---

## 10.4 最小可用版

**模式 B（纯 markdown 部署）**：只放 `SKILL.md` + `references/`，用本节的 §0.8 手工口径工作。
（`references/` 缺失时，`SKILL.md` 自带的「最小闭环」足以跑通建档→提问→录入，精度略低。）

**模式 A（完整部署）**：两张配置表 + 2–3 个主干学科骨架 + A/B 两轨 + `answering.md` 的提问流程。
C/D/E 三轨与 Playbook 可在使用中逐步启用。

---

手工模式下没有 `report.py`，需要看分布时按 `answering.md` §7 的八节自己聚合，
**八节一节都不能省**——尤其「正在生疏」和「待验证」两节，那是用户最需要看的。
