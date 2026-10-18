# 录入模板

> 复制对应模板填写，或直接交给智能体按模板录入。

---

## 知识点 `points/`

```yaml
---
id: kp_                      # 自动生成，不手填
name:                        # 同时就是文件名（可读，别用 id 命名文件）
subject:
course:
domain:                      # 域：10 选 1，见 _meta/domains.md；留空 = 未归类
transferable: 0.5            # 切面：可迁移性 0–1（>=0.7 即「通用与跨域方法」视图）
context: [专业]               # 切面：适用语境（专业 / 生活）
stage:                       # 可选：小学/初中/高中/大学/研究生/自学/职业
profile: foundation          # 衰减档位，见 _meta/decay_profiles.md
importance: 1.0              # 1.0 核心 / 0.6 一般 / 0.3 边缘
prior_exposure: medium       # 先验接触概率，**永不参与算分**，只用于「待验证清单」
raw_score: 0
current_score: 0
peak_score: 0
status: untouched            # 掌握等级，由 raw/current/peak 判定
last_verified_at:
origin: user                 # preset / inferred / user
rejected: false
evidence_ids: []
tags: []
---

## 我的理解


## 易错点 / 卡点
```

---

## 项目 `experience/projects/`

```yaml
---
id: prj_
name:
role:                        # 主导 / 参与 / 观察
started_at:
ended_at:
domains: []                  # 涉及哪些域（跨域边的原始信号）
context: [专业]
outcome:                     # 成功 / 部分 / 失败
touched_points: []           # 点亮了哪些知识点（写名字，边②）
skills: []                   # 动用了哪些技能（边③）
playbooks: []
blockers:                    # 卡在哪 —— 比"成功了"更有信息量
artifacts: []
---

## 背景与目标

## 我做了什么

## 结果与复盘

## 用到/印证了哪些知识点
```

---

## 技能 `experience/skills/`

```yaml
---
id: sk_
name: 信息检索
cluster: 信息处理            # 能力簇，不按学科组织
kind: composite             # composite 可分解 / tacit 隐性手感
requires: []                # 支撑它的知识点（写名字，边①）
experience: []              # 在哪些项目里用过（边③）
level: 0                    # 熟练度：只由行为证据推进，不从知识点分推导
last_used_at:
profile: durable            # 技能统一 730 天衰减
evidence_ids: []
---

## 现在会到什么程度

## 卡在哪
```

> 没有行为证据就是 `level: 0`。**「他应该会」不是证据。**

---

## 行动 `experience/actions/`

```yaml
---
id: act_
project_id: prj_
name:
flow:                        # 步骤用 → 连接
blocker:
resolution:
touched_points: []
---

## 细节
```

---

## 产物 `experience/artifacts/`

```yaml
---
id: art_
name:
type:                        # 文档/代码/设计稿/报告/数据/链接
path_or_url:
project_id: prj_
---
```

---

## Playbook `experience/playbooks/`

模板见 `templates/playbooks.md`（7 个流程类）。落盘时 `derived_from` **必须**填，
否则那只是通用建议，不是你的经验。

```yaml
---
id: pb_
name:
applicable_when:             # 什么情况该调出来（情境索引键）
derived_from: []             # 来源项目（写名字）
steps: []
anti_patterns: []            # 踩过的坑，经验里最有价值的部分
related_points: []
verified_count: 0
confidence: 0.8
---

## 适用场景

## 标准流程
1.
2.

## 已知坑位
-

## 关联知识点
-
```

---

## 智慧原则 `wisdom/`

```yaml
---
id: wis_
statement:                   # 一句话，可迁移
domain:                      # * 表示通用
confidence: 0.8
source: declared             # derived / declared
derived_from: []
counter:                     # 反例或适用边界
---
```

---

## 行为特征 `features/`

```yaml
---
id: feat_
feature:                     # 如：学习习惯-偏好实例驱动
value:
confidence: 0.7
source: observed             # observed / declared
evidence:
confirmed_by_user: false
---
```

---

## 问题日志 `questions/`

```yaml
---
id: q_
question:
touched_points: []
resolved:
asked_at:
derived_evidence: []
---
```

---

## 证据 `evidence/`（append-only）

```yaml
---
id: ev_
target_type: point          # point / skill / wisdom / feature
target_id: kp_
target_ids: []              # 全部目标：写多个 → 产生「共现」，横向边才有燃料
type: project_lead          # 见 _meta/weights.md
weight: 35
confidence: 0.9
role: ""                    # seed = 冷启动种子分（直接赋值，不累加）
direction: positive         # positive / negative / neutral
coefficient:                # 负向时填，如 0.85
occurred_at:
source_ref:                 # 关联的 prj_ / act_ / q_
note:
---
```

**撤销证据 = 追加一条反向证据，禁止删除原记录。**
