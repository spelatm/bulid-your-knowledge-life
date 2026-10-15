# 学科衰减档位表

> 半衰期 = 掌握度衰减到一半所需天数。按学科差异化配置。

## 档位定义

| 档位 | 半衰期 | 适用知识类型 | 理由 |
|---|---:|---|---|
| `volatile` | 45 天 | 词汇、外语、API 细节、版本号、具体参数 | 纯记忆，掉得最快 |
| `tooling` | 90 天 | 工具、框架、软件操作、命令行 | 不用就忘，且版本会变 |
| `foundation` | 180 天 | 数理基础、核心概念、专业基本功 | 理解了就不太会忘 |
| `methodology` | 365 天 | 方法论、思维方式、设计原则 | 一旦内化基本不掉 |
| `permanent` | ∞ | 母语、常识、基本生活技能 | 不参与衰减计算 |

## 学科 → 档位映射

| 学科 | 默认档位 | 备注 |
|---|---|---|
| 外语（词汇/语法点） | `volatile` | 阅读理解类可放宽到 `tooling` |
| 计算机科学 —— 框架与工具 | `tooling` | React、K8s 等 |
| 计算机科学 —— 理论与算法 | `foundation` | 数据结构、复杂度分析 |
| 数学 | `foundation` | 纯计算技巧可降为 `tooling` |
| 物理 / 化学 / 生物 | `foundation` | 实验操作细节用 `tooling` |
| 法律 / 医学（条文与剂量） | `volatile` | 会修订，需标注来源日期 |
| 法律 / 医学（原理） | `foundation` | — |
| 历史 / 地理（事实） | `tooling` | 年代、地名等 |
| 经济 / 管理 / 心理 | `methodology` | 理论模型 |
| 哲学 | `methodology` | — |
| 艺术与设计（技法） | `tooling` | 审美判断用 `methodology` |
| 职业技能（流程） | `methodology` | — |
| 母语 / 常识 | `permanent` | 不衰减 |

## 覆盖规则

优先级：**知识点自定义 > 课程覆盖 > 学科默认 > 全局默认（90 天）**

在知识点 frontmatter 中用 `profile: tooling` 覆盖。

## 计算

```
current_score = raw_score × 0.5^(Δt / half_life)
Δt = 今天 - last_verified_at
```

`permanent` 档位：`current_score = raw_score`，不衰减。

## 生疏判定

```
current ≤ peak × 0.6  且  peak ≥ 40   →  status = rusty
```

rusty 不是"不会"，而是"曾经会、现在可能废了"——全系统最有价值的状态位。
