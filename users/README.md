# 用户数据目录

每个用户一个子目录，存放其五轨档案。`_meta/`、`graph/`、`inference/` 为全局共享。

## 初始化

```bash
python3 scripts/init_profile.py --user <user_id> \
    --edu "<学历>" --job "<职业>" --region "<区域>"
```

## 目录结构

```
users/<user_id>/
├─ profile.md              背景信息与画像摘要
├─ edges.md                横向边登记簿（确认 / 拒绝记录）
├─ points/                 A 轨：知识点档案
├─ experience/
│  ├─ projects/            B 轨：项目
│  ├─ actions/             行动与流程
│  ├─ artifacts/           产物
│  ├─ playbooks/           提炼出的行动预案
│  └─ skills/              技能实体（熟练度由行为证据推进）
├─ wisdom/                 C 轨：智慧原则
├─ features/               D 轨：行为特征
├─ questions/              E 轨：问题日志
├─ reports/                生成的知识分布报告
└─ evidence/               证据流水（append-only）
```

> 知识点文件名 = 知识点名。用 Obsidian 打开 `users/<id>/` 就能看到分布与关联，
> 因为横向边写在正文的 `[[wikilink]]` 里。

## 测试用户

验证系统改动时，用 `__test__` 作为 user_id，测完删除：

```bash
python3 scripts/init_profile.py --user __test__ --edu "..." --job "..." --region "..."
python3 scripts/report.py --user __test__
rm -rf users/__test__
```

**禁止用真实用户数据做改动验证。**

## 铁律

- `evidence/` append-only，不修改不删除
- 撤销证据 = 追加反向证据
- 已有分数的知识点，重跑 `init_profile.py` 不会被覆盖（补充模式）
