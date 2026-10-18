# Playbook 模板（流程类经验）

> Playbook 回答 **know-when**：在什么情境下、按什么顺序做、哪些坑不要踩。
> 它**不是**知识点的另一种写法——知识点可以穷举，情境不能。

这七个模板来自 `graph/职业技能.md` 的「执行与协作 / 求职」两组。
那两组条目原来的身份错得最厉害：它们既不是学科知识（没有哪门课教
「复盘方法」），也不该算个人技能（技能分要靠行为证据推进），
而是**可复用的流程**——正好是 Playbook 的定义。

**模板不是数据。** 别直接复制进 `users/<id>/experience/playbooks/` 当既有经验：
没有 `derived_from`（从哪几个项目里长出来的）的 Playbook 是空壳。
正确用法是——某个项目结项时，agent 拿模板当骨架、用那次项目的真实卡点
把它填满，才落盘。

---

## 1. 任务拆解与排期

```yaml
name: 任务拆解与排期
applicable_when: 接到一个大到说不清第一周做什么的任务
steps:
  - 先写验收标准：什么算做完了（可被第三方判断）
  - 再倒推里程碑：每个里程碑要产出一个可看的东西
  - 再拆到「一个人一天能收尾」的粒度，拆不动的说明还没想清
  - 标出关键路径与外部依赖，其它都能挪
anti_patterns:
  - 一上来就排满甘特图，实际第一周就在等别人
  - 按「工时」拆而不按「产出」拆
related_points: []
derived_from: []      # ← 必须来自真实项目
verified_count: 0
```

## 2. 优先级判断

```yaml
name: 优先级判断
applicable_when: 同时有 5 件事，时间只够做 3 件
steps:
  - 先按「不做会怎样」分类：会死人 / 会延期 / 会被抱怨 / 没人注意
  - 再看「做了能不能改」：不可逆的先做对，可逆的先做完
  - 最后看「谁在等」：被别人的工作在等的那件事，优先级自动上浮
anti_patterns:
  - 用紧急/重要四象限自我安慰，然后做最容易的那件
  - 把「别人催得急」当成「重要」
related_points: []
derived_from: []
verified_count: 0
```

## 3. 会议组织

```yaml
name: 会议组织
applicable_when: 要开一个会，但说不清散会时应该得到什么
steps:
  - 先写一句会议产出："散会时我们要么定了 X，要么明确了为什么定不了"
  - 只请能改变这个产出的人；其余人发纪要
  - 会前把材料发出去并给出「需要你判断的那一个问题」
  - 会上只做决策，不做汇报；汇报放会前
anti_patterns:
  - 把会开成"同步进度"——那是文档的活
  - 没结论就散会，且不记录"为什么没结论"
related_points: []
derived_from: []
verified_count: 0
```

## 4. 文档沉淀

```yaml
name: 文档沉淀
applicable_when: 一件事做完，经验只在自己脑子里
steps:
  - 只写「下次遇到同样的事，我需要知道什么」，不写过程流水账
  - 三块：当时的前提 / 做了什么 / 现在回头看哪里可以不一样
  - 卡点单独成段——**卡住的地方比成功的地方更值得写**
  - 把文档链到相关知识点，否则三个月后没人找得到
anti_patterns:
  - 写成项目总结汇报（给领导看的），而不是给自己看的
  - 复制粘贴聊天记录当复盘
related_points: []
derived_from: []
verified_count: 0
```

## 5. 复盘方法

```yaml
name: 复盘方法
applicable_when: 项目刚结束，不论成败
steps:
  - 先对事实：目标是什么、实际结果是什么（用数字，不用形容词）
  - 再找归因：哪些是决策导致的，哪些是运气
  - 只保留能改的：不可控因素一句带过，不展开
  - 产出 1–3 条可复用的判断，写进 Playbook 或 C 轨智慧原则
anti_patterns:
  - 变成追责会（一旦追责，真话就没了）
  - 复盘的结论是"下次更努力"——那不是结论
related_points: []
derived_from: []
verified_count: 0
```

## 6. 风险管理

```yaml
name: 风险管理
applicable_when: 计划已定，准备开始执行
steps:
  - 列出「一旦发生就让计划作废」的 3 件事（不是 30 件）
  - 每件给出：早期信号是什么 / 信号出现时先做什么
  - 给不可逆的步骤留一次回退点
  - 把"最坏情况能不能接受"写下来，再决定要不要继续
anti_patterns:
  - 风险清单写成免责声明（列了 30 条，一条也没应对）
  - 只在项目开始时评估一次，之后不再看
related_points: []
derived_from: []
verified_count: 0
```

## 7. 求职准备

```yaml
name: 求职准备
applicable_when: 要投简历 / 要面试一个明确岗位
steps:
  - 先把岗位要求拆成"它要我证明什么"的清单
  - 每条要求配一个自己做过的事（没做过的就不要假装有）
  - 简历只写能被追问三层的经历，其它的删掉
  - 面试前准备 3 个"我卡住了怎么解的"故事，比背题有用
anti_patterns:
  - 一份简历投所有岗位
  - 把课程作业写成项目经历
related_points: []
derived_from: []
verified_count: 0
```

---

## 落盘方式

模式 A：

```bash
python3 scripts/skill.py --user <id> --playbook 复盘方法 \
    --from <prj_id> --step "..." --anti "..." --point 消息传递机制
```

模式 B（手工）：把上面的 yaml 复制到
`users/<id>/experience/playbooks/<名字>.md`，**必须**填 `derived_from`——
填不出来说明这次还不是经验，只是一条通用建议。
