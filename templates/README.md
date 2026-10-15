# 录入模板

> 复制对应模板填写，或直接交给智能体按模板录入。

---

## 知识点 `points/`

```yaml
---
id: kp_                      # 自动生成，不手填
name:
subject:
course:
stage:                       # 可选：小学/初中/高中/大学/研究生/自学/职业
profile: foundation          # 衰减档位，见 _meta/decay_profiles.md
raw_score: 0
current_score: 0
peak_score: 0
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
role:                        # 主导 / 参与 / 协助
started_at:
ended_at:
domain:
capability_tags: []
artifact_ids: []
action_ids: []
---

## 背景与目标

## 我做了什么

## 结果与复盘

## 用到/印证了哪些知识点
```

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

```yaml
---
id: pb_
name:
applicable_when:             # 什么情况该调出来
derived_from: []             # 来源项目 id
related_points: []
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
target_type: point          # point / wisdom / feature
target_id: kp_
type: project_lead          # 见 _meta/weights.md
weight: 35
confidence: 0.9
direction: positive         # positive / negative
coefficient:                # 负向时填，如 0.85
occurred_at:
source_ref:                 # 关联的 prj_ / act_ / q_
note:
---
```

**撤销证据 = 追加一条反向证据，禁止删除原记录。**
