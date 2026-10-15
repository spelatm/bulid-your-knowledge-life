# 数据结构定义

> 五轨统一字段规范。所有文件 YAML frontmatter + Markdown 正文。

---

## A 轨 · 知识点 `points/*.md`

```yaml
---
id: kp_<8位哈希>
name: 特征值分解
subject: 数学
course: 线性代数
stage: 大学                    # 可选
profile: foundation           # 衰减档位
importance: 1.0               # 核心1.0 / 一般0.6 / 边缘0.3，学科聚合加权用
raw_score: 72.0
current_score: 58.3
peak_score: 78.0
last_verified_at: 2025-03-11
origin: preset                # preset / inferred / user
rejected: false               # 用户否认的推断项
evidence_ids: [ev_0012, ev_0047]
tags: [核心, 考试重点]
---
```

正文：该知识点的个人化备注、当时怎么理解的、易错点。可为空。

---

## B 轨 · 项目 `experience/projects/*.md`

```yaml
---
id: prj_<8位哈希>
name: 支付系统重构
role: 主导
started_at: 2024-06
ended_at: 2024-11
domain: 后端
capability_tags: [高并发, 分布式事务, 系统重构]
artifact_ids: [art_0003]
action_ids: [act_0011, act_0012]
---
```

正文：背景、目标、结果、复盘。

### 行动 `experience/actions/*.md`
```yaml
---
id: act_<8位哈希>
project_id: prj_xxxx
name: 拆分账务核心
flow: 梳理依赖 → 抽接口 → 灰度切流 → 下线旧逻辑
blocker: 双写一致性
resolution: 最终一致 + 对账补偿
touched_points: [kp_0021, kp_0088]
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
applicable_when: 老系统需要重写但业务不能停
derived_from: [prj_xxxx, prj_yyyy]
related_points: [kp_0021]
confidence: 0.85
---
```
正文分四节：适用场景 / 标准流程 / 已知坑位 / 关联知识点。

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
target_type: point          # point / wisdom / feature
target_id: kp_0021
type: project_lead          # 见 weights.md
weight: 35
confidence: 0.9
direction: positive         # positive / negative
coefficient: null           # 负向证据时填
occurred_at: 2024-09-20
source_ref: prj_xxxx
note: 主导支付重构账务拆分
---
```

**append-only**：证据只追加、不修改、不删除。分数由证据重算得出，任何时刻可审计。
如需撤销，追加一条反向证据，而非删除原记录。
