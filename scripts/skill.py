#!/usr/bin/env python3
"""技能实体（B 轨 `experience/skills/`）：建、查、连、算错位。

**技能分与知识分是两套独立计算，不互相推导。**

| | 知识（A 轨） | 技能（B 轨） |
|---|---|---|
| 分数来自 | 学习类证据（读过 / 理解 / 推导过） | 行为类证据（写过 / 独立完成 / 优化过 / 教过别人） |
| 字段 | `raw_score` / `current_score` | `level` / `last_used_at` |
| 衰减 | 45 / 90 / 180 / 365 / ∞ | `durable`（730 天） |

两者相减得到 `gap`——**这套系统独有的指标**：

```
gap = level(技能) − mean(current_score(requires 里的知识点))
```

| gap | 含义 | agent 该做什么 |
|---|---|---|
| > +20 | 手熟，原理淡了 | 补原理、给推导 |
| −20 ~ +20 | 知行相当 | 正常讲 |
| < −20 | 学过，没实践过 | 给练习、少讲理论 |

用法：
    python3 scripts/skill.py --user u001 --seed                # 抄预置技能簇
    python3 scripts/skill.py --user u001 --add "论文复现" --cluster 学术研究 \
        --kind composite --requires "消息传递机制,谱图理论"
    python3 scripts/skill.py --user u001 --requires "论文复现" \
        --points "消息传递机制,谱图理论"
    python3 scripts/skill.py --user u001 --list                # 含 gap
    python3 scripts/skill.py --user u001 --project "论文复现：GNN 过度平滑" \
        --role 主导 --domains "信息与计算技术" --outcome 部分
    python3 scripts/skill.py --user u001 --playbook 复盘方法 \
        --from "论文复现：GNN 过度平滑" --step "先跑通官方代码" \
        --anti "一上来就自己重写" --point 消息传递机制
"""
import os
import sys
import argparse
import collections
import core

SKILL_DIR = ("experience", "skills")
GAP_HI, GAP_LO = 20.0, -20.0


def _udir_skill(udir):
    return os.path.join(udir, *SKILL_DIR)


def _names(v):
    if isinstance(v, str):
        return [x.strip() for x in v.replace("，", ",").split(",") if x.strip()]
    return [str(x) for x in (v or [])]


# ---------- 技能 ----------

def new_skill(udir, name, cluster="", kind="composite", requires=None,
              pidx=None, existing=None):
    """建一个技能实体。`pidx`/`existing` 是可选的复用索引——

    批量播种时别再逐条重扫：500 个知识点 × 23 个技能 = 一万多次读盘，
    会把一次 `--seed` 拖成两分钟。
    """
    if existing is not None:
        if name in existing:
            return f"技能「{name}」已存在，跳过"
    elif name in core.index_skills(udir)["by_name"]:
        return f"技能「{name}」已存在，跳过"
    path = os.path.join(_udir_skill(udir), core.safe_name(name) + ".md")
    meta = {
        "id": core.new_id("sk"), "name": name,
        "cluster": cluster or "未分簇",
        "kind": kind if kind in core.KINDS else "composite",
        "requires": requires or [],
        "experience": [],
        "level": 0.0, "last_used_at": "", "profile": "durable",
        "evidence_ids": [],
    }
    body = f"# {name}\n\n## 现在会到什么程度\n\n## 卡在哪\n"
    core.write_md(path, meta, _render(udir, meta, body, pidx))
    if existing is not None:
        existing.add(name)
    return f"已建技能「{name}」（{meta['cluster']} / {meta['kind']}）"


def _render(udir, meta, body, pidx=None):
    """技能正文的托管块：requires 里的知识点 → wikilink（Obsidian 才看得见）。"""
    pidx = pidx or core.index_points(udir)
    entries = []
    for n in _names(meta.get("requires")):
        hit = pidx["by_name"].get(n)
        if not hit:
            continue
        stem = os.path.splitext(os.path.basename(hit[0]))[0]
        entries.append((n, stem, ""))
    entries.sort(key=lambda e: e[0])
    return core.set_related(body, entries, title="支撑它的知识点")


def set_requires(udir, skill_name, points):
    idx = core.index_skills(udir)
    hit = core.find_skill(udir, skill_name, idx)
    if not hit:
        return f"未找到技能「{skill_name}」"
    path, meta, body = hit
    pidx = core.index_points(udir)
    ok, miss = [], []
    for n in points:
        (ok if n in pidx["by_name"] else miss).append(n)
    meta["requires"] = ok
    core.write_md(path, meta, _render(udir, meta, body, pidx))
    core.invalidate(udir)
    out = f"「{meta['name']}」requires ← {len(ok)} 个知识点"
    if miss:
        out += f"（未找到：{'、'.join(miss)}）"
    return out


def seed(udir):
    """把 skills/ 预置目录抄进用户档案。熟练度 0——没行为证据就是 0。"""
    cat = core.load_skill_catalog()
    existing = set(core.index_skills(udir)["by_name"])
    before = len(existing)
    for item in cat:
        new_skill(udir, item["name"], item["cluster"], item["kind"],
                  existing=existing)
    added = len(existing) - before
    return (f"预置技能簇：新增 {added} 个，已有 {len(cat) - added} 个跳过"
            f"（熟练度一律 0，等行为证据）")


def gap_of(udir, meta, pidx):
    """返回 (gap, 平均知识分, 缺口数)；requires 为空则 gap=None。"""
    names = _names(meta.get("requires"))
    if not names:
        return None, None, 0
    vals, missing = [], 0
    for n in names:
        hit = pidx["by_name"].get(n)
        if not hit:
            missing += 1
            continue
        m = hit[1]
        raw = float(m.get("raw_score", 0) or 0)
        cur, _ = core.apply_decay(raw, m.get("last_verified_at"),
                                  str(m.get("profile", "foundation")))
        vals.append(cur)
    if not vals:
        return None, None, missing
    mean = sum(vals) / len(vals)
    return float(meta.get("level", 0) or 0) - mean, mean, missing


def verdict(gap):
    if gap is None:
        return "—", "requires 为空：要么是 tacit 技能（正常），要么还没连"
    if gap > GAP_HI:
        return "手熟原理淡", "补原理、给推导，别只讲操作"
    if gap < GAP_LO:
        return "纸上谈兵", "给练习、给动手任务，少讲理论"
    return "知行相当", "正常讲"


def list_skills(udir):
    idx = core.index_skills(udir)
    if not idx["items"]:
        return "还没有技能实体。先跑 --seed，或用 --add 建一个。"
    pidx = core.index_points(udir)
    groups = collections.defaultdict(list)
    for _p, m, _b in idx["items"]:
        groups[str(m.get("cluster", "未分簇"))].append(m)
    out = [f"技能 {len(idx['items'])} 个（熟练度由行为证据推进，与知识点分互不推导）", ""]
    out.append("| 技能 | 簇 | kind | 熟练度 | 知识均分 | gap | 判读 |")
    out.append("|---|---|---|---:|---:|---:|---|")
    for cl in sorted(groups):
        for m in sorted(groups[cl], key=lambda x: -float(x.get("level", 0) or 0)):
            g, mean, miss = gap_of(udir, m, pidx)
            v, _adv = verdict(g)
            out.append(
                f"| {m.get('name')} | {cl} | {m.get('kind')} | "
                f"{float(m.get('level', 0) or 0):.0f} | "
                f"{'—' if mean is None else f'{mean:.0f}'} | "
                f"{'—' if g is None else f'{g:+.0f}'} | {v} |")
    return "\n".join(out)


# ---------- 经验：项目 / Playbook ----------

def new_project(udir, name, role="参与", domains=None, context=None,
                outcome="", blockers=""):
    pdir = os.path.join(udir, "experience", "projects")
    path = os.path.join(pdir, core.safe_name(name) + ".md")
    if os.path.exists(path):
        return f"项目「{name}」已存在"
    meta = {
        "id": core.new_id("prj"), "name": name, "role": role,
        "started_at": core.TODAY.isoformat()[:7], "ended_at": "",
        "domains": domains or [], "context": context or ["专业"],
        "outcome": outcome,
        "touched_points": [], "skills": [], "playbooks": [],
        "blockers": blockers, "artifacts": [],
    }
    body = ("# " + name + "\n\n## 背景与目标\n\n## 我做了什么\n\n"
            "## 卡在哪\n\n## 结果与复盘\n")
    core.write_md(path, meta, body)
    return f"已建项目「{name}」（{role}）"


def new_playbook(udir, name, derived_from, steps, anti, points,
                 applicable_when=""):
    pdir = os.path.join(udir, "experience", "playbooks")
    path = os.path.join(pdir, core.safe_name(name) + ".md")
    exists = os.path.exists(path)
    meta, body = core.read_md(path)
    if not exists:
        meta = {"id": core.new_id("pb"), "name": name,
                "applicable_when": applicable_when or name,
                "derived_from": [], "steps": [], "anti_patterns": [],
                "related_points": [], "verified_count": 0,
                "evidence_ids": []}
        body = f"# {name}\n\n## 适用场景\n\n## 标准流程\n\n## 已知坑位\n\n## 关联知识点\n"
    for f in ("derived_from", "steps", "anti_patterns", "related_points"):
        meta[f] = _names(meta.get(f))
    for v in derived_from or []:
        if v not in meta["derived_from"]:
            meta["derived_from"].append(v)
    for v in steps or []:
        if v not in meta["steps"]:
            meta["steps"].append(v)
    for v in anti or []:
        if v not in meta["anti_patterns"]:
            meta["anti_patterns"].append(v)
    for v in points or []:
        if v not in meta["related_points"]:
            meta["related_points"].append(v)
    if exists:
        meta["verified_count"] = int(meta.get("verified_count", 0) or 0) + 1
    core.write_md(path, meta, body)
    return (f"{'更新' if exists else '已建'} Playbook「{name}」"
            f"（来源 {len(meta['derived_from'])} 个项目，"
            f"验证 {meta['verified_count']} 次）")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--seed", action="store_true")
    p.add_argument("--add", metavar="技能名")
    p.add_argument("--cluster", default="")
    p.add_argument("--kind", default="composite")
    p.add_argument("--requires", metavar="技能名")
    p.add_argument("--points", default="", help="知识点名，逗号分隔")
    p.add_argument("--list", action="store_true")
    p.add_argument("--project", metavar="项目名")
    p.add_argument("--role", default="参与")
    p.add_argument("--domains", default="")
    p.add_argument("--outcome", default="")
    p.add_argument("--blockers", default="")
    p.add_argument("--playbook", metavar="Playbook名")
    p.add_argument("--from", dest="derived", action="append", default=[])
    p.add_argument("--step", action="append", default=[])
    p.add_argument("--anti", action="append", default=[])
    p.add_argument("--point", action="append", default=[])
    a = p.parse_args()

    udir = core.user_dir(a.user)
    if not os.path.isdir(udir):
        print(f"用户 {a.user} 不存在")
        return 1

    if a.seed:
        print(seed(udir))
    elif a.add:
        print(new_skill(udir, a.add, a.cluster, a.kind, _names(a.points)))
    elif a.requires:
        print(set_requires(udir, a.requires, _names(a.points)))
    elif a.project:
        print(new_project(udir, a.project, a.role, _names(a.domains),
                          None, a.outcome, a.blockers))
    elif a.playbook:
        print(new_playbook(udir, a.playbook, a.derived, a.step, a.anti, a.point))
    elif a.list:
        print(list_skills(udir))
    else:
        p.error("需要一个动作：--seed / --add / --requires / --list / "
                "--project / --playbook")
    return 0


if __name__ == "__main__":
    sys.exit(main())
