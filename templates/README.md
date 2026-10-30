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

## 概要

> 一句话：（30 字以内说清它是什么）

- [[#详解]] — 它是什么、怎么运转
- [[#我的掌握]] — 分数、上次接触、证据构成
- [[#我的经历]] — 哪次实践用到了它

## 详解

<!-- 六段结构：顺序固定，不适用的一段直接不写，不要留空标题。
     ① 它是什么（划边界）② 解决什么问题 ③ 怎么运转
     ④ 怎么用 ⑤ 实例 ⑥ 与相邻概念的边界 -->

### 它是什么（先划边界）

| 常见说法 | 对不对 | 为什么 |
|---|---|---|
| （一句流行但错误的说法） | ✗ | （错在哪） |
| （准确的说法） | ✓ | （为什么准） |

### 它解决什么问题

（没有它会怎样 → 它把哪一段麻烦吃掉了）

| 方案 | 启动 | 开销 | 隔离 | 密度 |
|---|---|---|---|---|
| | | | | |

### 它怎么运转

1. （第一步：谁做了什么）
2. （第二步）
3. （第三步）

### 怎么用

| 目的 | 命令 / 接口 |
|---|---|
| | |

```bash
# 这条命令在干什么
（完整可复制的命令）
```

### 实例

> [!example] （场景名）
> （一句话说明这个例子要验证什么）

```bash
（命令）
```
```
（真实输出，几行即可）
```

（这行输出说明了什么）

### 与相邻概念的边界

| 概念 | 差别在哪 | 什么时候用它 |
|---|---|---|
| | | |

## 易错点

| 坑 | 为什么踩 | 怎么防 |
|---|---|---|
| | | |

## 经验与判断

| 场景 | 判断 |
|---|---|
| | |

## 我的掌握

<!-- auto:score:start -->
（脚本自动生成，别手改）
<!-- auto:score:end -->

## 我的经历

<!-- auto:exp:start -->
（脚本从证据自动生成，别手改）
<!-- auto:exp:end -->

## 关联

## 更新记录
```

> **正文分工**（3.10.0 起）：`概要` 是索引，指向下面真实存在的章节；
> `详解 / 易错点 / 经验与判断` 是内容，可以手写，也可以让 agent 写完后标 `content_source`；
> `我的掌握 / 我的经历` 由证据算出来，**不许手填**。
> 章节顺序固定，`## 关联` 里的托管块必须整块待在本章节内，不要让它跨界。
>
> **排版硬规则**（3.10.2 起，为「一眼能扫、细看能懂」）：
> 1. **三项以上且彼此有对应关系 → 一律用表格**，不要堆项目符号
> 2. **每条命令都放进代码块**，块上一行说明它在干什么；有输出的给几行真实输出
> 3. 最致命的坑用 `> [!warning]`，实例用 `> [!example]`（Obsidian 渲染成彩色块，
>    纯文本下也就是一段引用，不会坏）
> 4. 关键结论**单独成行并加粗**，不超过两行；一段里只讲一件事
> 5. 表格单元格里不要出现半角竖线，一律写全角 `｜`。**没有例外**：
>    命令带管道符（`|`）时就别放进表格，改放代码块——管道必须半角才能执行，
>    而表格单元格容不下半角竖线，这两件事不能兼得
> 6. 公式用 `$…$` / `$$…$$`（Obsidian 与 GitHub 都原生渲染），不用 `\(…\)`
> 7. 图片放 `users/<id>/assets/`，用标准 markdown 相对路径 `![](../assets/…)`，
>    **alt 文字必写**；不用 `![[…]]`（Obsidian 专有）
> 8. 外链只给「内容标识」型地址（RFC / DOI / 官方文档），每条后跟一句「它讲什么」；
>    短链、`?utm_*`、搜索结果页、iframe 视频一律不用。细节见
>    `references/recording.md` §6.8「外链：怎么挑一个十年后还能打开的网址」

---

## 素材 `assets/`

知识点里要放图、录音、录屏时，文件都放这里，正文用相对路径引用。

```
users/<id>/assets/
  2026-10-cgroup-oom.png          ← YYYY-MM-语义名.扩展名
  2026-10-咨询录音.m4a
  README.md                        ← 命名与引用规矩
```

| 想放什么 | 怎么放 | 引用写在哪 |
|---|---|---|
| 公式 | 不占文件，直接写 LaTeX | `$…$` 行内 / `$$…$$` 独立 |
| 图片 / 截图 | 存 `assets/` | `![alt 文字](../assets/2026-10-xxx.png)` |
| 音频 / 视频 | 存 `assets/` | `<audio controls src="…"></audio>` + 一行兜底链接 |
| 外部网页 | 不下载，只存链接 | `[标题](https://…) — 一句它讲什么` |

> **为什么不把网页存成 PDF 或截图放进来**：体积大、检索不了、还会过期。
> 存**链接 + 一句话摘要**，链接死了靠那句话重新找。这条判断适合绝大多数情况。
>
> **`assets/` 不进 git**（`users/*` 已被忽略）。要公开带图的档案，先显式确认。

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
