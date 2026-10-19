# 手工口径：没有脚本时怎么做

> **管什么**：在没有 `scripts/` 的环境里，把脚本的活儿全接过来自己干。
> **何时读**：部署的是纯 markdown 版本，或 `python3` 不可用 / 脚本报错需要降级。
> **读完回**：`SKILL.md` §1 场景路由表。

---

## 0.8 手工口径

> 没有 `scripts/`、`graph/`、`_meta/` 时，**本节取代前面所有命令**。
> 你要扮演脚本：自己建目录、自己算分、自己写文件。
> **算法与完整仓库版本完全一样**（`model.md` §3），算出来不一样就是算错了，不是有两套算法。

### ① 目录结构

缺失就建，路径相对本 Skill 根目录：

```
users/<user_id>/
├─ profile.md          档案头，格式见 ②
├─ points/             一个知识点一个文件，文件名＝知识点名，见 ③
├─ evidence/           证据，一条一个文件，只增不改
├─ questions/          问题日志
├─ experience/         projects/ actions/ artifacts/ playbooks/ skills/
├─ wisdom/  features/  （用到再建）
├─ edges.md            横向边决策簿：谁、何时、拒过哪对
└─ reports/            只有跑报告并保存时才产生
```

### ② `profile.md`

**字段名必须与完整仓库版本一致**，否则 `bootstrap.py` 会误判为 `partial`：

```yaml
---
education: 计算机本科        # 学历 / 专业，照用户原话（字段名固定为 education）
occupation: 前端工程师 5 年   # 职业 / 年限（字段名固定为 occupation）
region: 杭州                # 区域（字段名固定为 region）
user_id: default
created_at: 2026-10-15
updated_at: 2026-10-15
onboarding: ready           # 三项齐 = ready，缺项 = partial（字段名固定为 onboarding）
---

# default 的能力档案

- 学历：计算机本科
- 职业：前端工程师 5 年
- 区域：杭州
```

> 三项取值出现 `""`、`未填`、`未知`、`-`、`—` 之一，即视为该项缺失（与脚本口径一致）。

### ③ `points/<知识点名>.md`

**文件名＝知识点名**（如 `消息传递机制.md`），**不要用 id 当文件名**——
档案要能被 Obsidian 直接打开阅读，一堆哈希文件名在那边没法看、没法搜、没法连。
`id` 仍写在 frontmatter，脚本不依赖文件名定位。
（名字里的 `/ : * ? " < > |` 换全角；跨学科重名加「（学科）」后缀。）

```yaml
---
id: kp_a1b2c3d4
name: 消息传递机制
subject: 计算机科学        # 学科，自己归纳，粒度保持稳定
course: 图神经网络         # 课程 / 方向
domain: 信息与计算技术      # 域，10 选 1，只作索引；空 = 未归类（见 _meta/domains.md）
transferable: 0.5         # 切面：可迁移性 0–1，>=0.7 归入「通用与跨域方法」视图
context: [专业]            # 切面：适用语境（专业 / 生活）
importance: 1.0           # 1.0 核心 / 0.6 一般 / 0.3 边缘
profile: foundation       # 衰减档位，见 model.md §3.3
prior_exposure: medium    # 先验接触概率，永不参与算分，只用于「待验证清单」
raw_score: 0              # 累计分
current_score: 0          # 当前分
peak_score: 0             # 历史最高
last_verified_at: ""      # 无证据留空，有证据填发生日期
origin: inferred          # preset / inferred / user
rejected: false
evidence_ids: []          # 支撑这个分数的证据 id
status: aware             # 状态名，按 model.md §3.4 算
tags: []                  # 可放强度标签，如 [strong, 网络检索]
---

# 消息传递机制

## 我的理解

## 易错点 / 卡点
```

### ④ `evidence/<id>.md`

只增不改，一条一个文件，`id` 形如 `ev_9f8e7d6c`：

```yaml
---
id: ev_9f8e7d6c
target_type: point        # point / skill / wisdom / feature
target_id: kp_a1b2c3d4    # 主目标（老脚本只认这个字段）
target_ids: [kp_a1b2c3d4, kp_f9e8d7c6]   # 全部目标，可点亮多个点
type: project_lead        # 见 model.md §3.1 / §3.2
weight: 35                # 正向填权重；负向可留空
confidence: 0.9
role: ""                  # 填 seed 表示冷启动种子分（直接赋值，不累加）
direction: positive       # positive / negative / neutral
coefficient:              # 仅负向填，如 0.85
occurred_at: 2026-10-15
source_ref:               # 关联的项目 id，或联网来源 URL
note: 主导支付链路重构
---
```

写完证据**必须回填**知识点文件的 `evidence_ids`、`raw_score`、`current_score`、
`peak_score`、`status`、`last_verified_at`。两处不一致时以证据为准重算。

> **`target_ids` 写多个值，是系统唯一能长出结构的地方。**
> 一条证据同时点亮 A 和 B 即一次共现；共现够了才谈得上「这两条该连」。
> 只写单值，档案永远是一张平铺的表。

### ⑤ 算分：照公式推，不要估

```
加分    累计分 += (100 − 累计分) × 权重/100 × 置信度     ← 权重与置信度查 model.md §3.1
扣分    累计分 ×= 系数                                   ← 系数查 §3.2
打折    当前分 = 累计分 × 0.5^(距上次验证天数 / 半衰期)     ← 半衰期查 §3.3
定状态  照 §3.4 判；累计分变了同步更新历史最高
```

**算例**：某知识点累计分为 0，用户主导过一次相关项目（`project_lead`，权重 35，置信度 0.9）：

```
累计分 = 0 + (100 − 0) × 0.35 × 0.9 = 31.5
状态   = 31.5 落在 26–50 → 「理解原理」
历史最高 = 31.5
```

### ⑥ 落盘节奏

- **一次对话结束前批量写**，不要每说一句落一次盘
- 同一会话内**同一知识点只记一条证据**，把 note 写完整
- 写文件失败 → 告知用户一次，继续正常回答，**不要卡住**

### ⑦ 手工建横向边（对应 `recording.md` §6.6）

1. 扫 `evidence/`，看哪些证据的 `target_ids` 同时含两个知识点 → 记一次共现
2. 同一对达 3 次**且**同域 → 可直接连；否则**先问用户**，一次最多 3 对
3. 连法：两边 `related: [名字]` 各加一条，正文追加 `## 关联` 与 `- [[对方名字]]`
   （Obsidian 靠正文链接画图）
4. 用户拒绝 → 记进 `edges.md`，**这一对以后不再建议**

### ⑧ 手工建技能（对应 `recording.md` §6.7）

技能放 `experience/skills/`，**熟练度 `level` 只来自行为证据**（做过 / 教过别人 / 有产物），
不从知识点分推导。

字段：`name` / `cluster` / `kind`(composite|tacit) / `requires`(知识点名) /
`experience`(项目名) / `level` / `last_used_at` / `profile: durable` / `evidence_ids`

`错位 = level − requires 里知识点的当前分均值`：> +20 补原理，< −20 给练习。

---

## 完整仓库长什么样（对照用）

```
knowledge-profile/
├─ SKILL.md              主文档：角色 / 不变量 / 环境探测 / 场景路由表
├─ references/           子文档：按会话阶段拆，用到才读（索引在 SKILL.md）
├─ CHANGELOG.md          系统变更记录（改进必写）
├─ _meta/                配置层：改这里，不改代码
├─ graph/                预置学科骨架（只装能被某门课教的东西）
├─ skills/               预置技能簇（按能力组织，不按学科）
├─ inference/            背景推断模板
├─ templates/            各类录入模板（含 playbooks.md 流程模板）
├─ scripts/              可执行脚本（完整仓库才有）
├─ design/               设计草案与迁移记录
├─ archive/              只存 git 表达不了的东西（如用户数据快照）
└─ users/<user_id>/      每用户隔离
   ├─ profile.md
   ├─ edges.md           横向边登记簿（决策与拒绝清单）
   ├─ points|experience|wisdom|features|questions|reports|evidence
   └─ experience/skills/ 技能实体
```

**为什么技能不在 `graph/` 里**：`graph/` 是**学科**骨架，铁纪律是「装得进某门课」。
「复盘方法」属于哪个学科？没有答案。硬塞进去的代价是整个骨架失去可比性——
一旦混进不属于任何课程的东西，就没法再用它判断「这个人的知识结构比别人宽还是窄」。
3.4.0 之前的 `graph/职业技能.md` 就是这么错的，3.5.0 拆掉，
逐条去向见 `design/职业技能分流-mapping.md`。

---

## 10.4 最小可用版

**纯 markdown 部署**：放 `SKILL.md` + `references/`，按本文的手工流程工作。
（连 `references/` 都没有时，`SKILL.md` 自带的「最小闭环」也够跑通建档 → 提问 → 录入，精度略低。）

**完整仓库部署**：两张配置表 + 2–3 个主干学科骨架 + A/B 两轨 + `answering.md` 的提问流程。
C/D/E 三轨与 Playbook 可在使用中逐步启用，不必一次配齐。

---

手工模式没有 `report.py`，要看分布时按 `answering.md` §7 的八节自己聚合。
**八节一节都不能省**，尤其「正在生疏」和「待验证」——
用户真正想知道的往往不是「我懂多少」（他心里有数），
而是「什么正在悄悄溜走」和「哪些是我猜的、哪些是真的」。
