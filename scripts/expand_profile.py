#!/usr/bin/env python3
"""联网扩展档案：把智能体联网检索出的知识点灌进用户档案。

用途（对应 SKILL.md §0.7）：
用户说出自己的背景后，静态的 inference/*.md 映射表覆盖不到时，
由智能体联网检索（培养方案、岗位能力模型、行业资料、教材目录…），
把检索结果整理成 JSON，本脚本负责：

  1. 与 graph/ 骨架 + 别名匹配：命中 → 给已有的 0 分知识点赋分
  2. 未命中 → 按 JSON 里的 subject/course 建新知识点条
  3. 每个赋分点写入一条 append-only 证据（含来源 URL），可追溯、可审计
  4. 输出"向用户批量确认"的话术

用法：
    python3 expand_profile.py --user default --input inferences.json
    python3 expand_profile.py --user default --input inferences.json --dry-run
    python3 expand_profile.py --user default --input inferences.json --force

输入 JSON 格式：
{
  "background": "2026级燕山大学…研究生 / 学生 / 秦皇岛",
  "sources": [
    {"url": "https://…", "title": "计算机技术专业硕士培养方案", "used_for": "课程体系"}
  ],
  "points": [
    {"name": "Transformer 与注意力", "strength": "strong",
     "course": "人工智能", "subject": "计算机科学",
     "reason": "人工智能专业硕士核心课", "source": "https://…"},
    {"name": "科研伦理与学术规范", "strength": "likely",
     "subject": "其他", "course": "研究生科研素养",
     "reason": "培养方案必修环节", "source": "https://…"}
  ]
}

strength 取 strong / likely / possible，对应冷启动种子分 50 / 30 / 20
（口径与 inference/README.md 一致：strong 40–60、likely 25–35、possible 20）。

注意：冷启动种子分走的是**配置表**而非证据累加——新用户没有历史证据，
若按 _meta/weights.md 的推断权重（个位数）赋分，档案会长期停在"未触及"
边缘而不可用。证据条用于记录来源与后续审计，其 weight 记为实际使用的种子分。
"""
import os
import re
import glob
import json
import argparse
import core

SEED = {"strong": 50.0, "likely": 30.0, "possible": 20.0}
CONF = {"strong": 0.7, "likely": 0.55, "possible": 0.4}

TAG_SOURCE = "网络检索"


def load_skeleton():
    """返回 (按名索引, 全部条目, 课程索引)。

    课程索引是必要的：检索引擎常返回「软件工程」这种**课程名**，
    而骨架里它是课程不是知识点。不认课程名就会在「其他」里凭空多一条。
    """
    items = core.parse_graph()
    by_name = {g["name"]: g for g in items}
    courses = {}
    for g in items:
        c = str(g.get("course", "") or "")
        if c and c not in courses:
            courses[c] = {"name": c, "subject": g["subject"], "course": c,
                          "importance": 0.6, "profile": g.get("profile",
                                                               "foundation"),
                          "aliases": []}
    return by_name, items, courses


def match_skeleton(name, by_name, items, courses=None):
    """把检索出的知识点名对到骨架上。返回 (骨架条目, 命中方式)。"""
    courses = courses or {}
    if name in by_name:
        return by_name[name], "同名"
    norm = re.sub(r"[\s·/／\-—_()（）]", "", name)
    for g in items:
        if re.sub(r"[\s·/／\-—_()（）]", "", g["name"]) == norm:
            return g, "同名(忽略符号)"
    for g in items:
        for a in g.get("aliases", []):
            if a == name or (len(a) >= 3 and a in name) or (
                    len(name) >= 3 and name in a):
                return g, f"别名({a})"
    if name in courses:
        return dict(courses[name]), "骨架课程名"
    # 最后做一次保守的子串匹配，要求重叠部分足够长
    for g in items:
        gn = g["name"]
        if len(name) >= 4 and (name in gn or gn in name):
            return g, "包含"
    return None, ""


def index_existing(udir):
    """一次性把用户已有的知识点建成索引：{名字: (路径, meta, body)}。

    逐个检索项去 glob 全量知识点是 O(检索项 × 知识点)，几十条就能卡住；
    建一次索引即可。
    """
    idx = {}
    for path in glob.glob(os.path.join(udir, "points", "*.md")):
        meta, body = core.read_md(path)
        name = str(meta.get("name", ""))
        if name and name not in idx:
            idx[name] = (path, meta, body)
    return idx


def find_existing(index, name):
    return index.get(name, (None, None, None))


def write_evidence(udir, kp_id, strength, note, url):
    ev_id = core.new_id("ev")
    core.write_md(
        os.path.join(udir, "evidence", f"{ev_id}.md"),
        {"id": ev_id, "target_type": "point", "target_id": kp_id,
         "type": "web_inferred", "weight": SEED[strength],
         "confidence": CONF[strength], "direction": "positive",
         "coefficient": "", "occurred_at": core.TODAY.isoformat(),
         "source_ref": url or "", "note": note or ""},
    )
    return ev_id


def expand(user_id, input_path, dry_run=False, force=False):
    udir = core.user_dir(user_id)
    if not os.path.isdir(udir):
        return f"用户 {user_id} 不存在，先跑 init_profile.py 建档。"

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    points = data.get("points") or []
    sources = data.get("sources") or []
    if not points:
        return "输入里没有 points，未做任何改动。"

    by_name, items, courses = load_skeleton()
    index = index_existing(udir)
    scored, created, skipped, added_ev = [], [], [], 0

    for p in points:
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        strength = str(p.get("strength", "likely")).lower()
        if strength not in SEED:
            strength = "likely"
        reason = str(p.get("reason", "") or "")
        url = str(p.get("source", "") or "")
        seed = SEED[strength]

        g, how = match_skeleton(name, by_name, items, courses)
        target = g["name"] if g else name

        path, meta, body = find_existing(index, target)
        if meta is not None and float(meta.get("raw_score", 0) or 0) > 0 and not force:
            skipped.append(f"{target}（已有分数，跳过）")
            continue

        if dry_run:
            (scored if meta is not None else created).append(
                f"{target}　{strength}　{how or '新建'}")
            continue

        if meta is None:
            # 骨架外的知识点：优先用骨架给的学科/课程，其次用 JSON 指定的
            kp_id = core.new_id("kp")
            subject = str((g or {}).get("subject") or p.get("subject") or "其他")
            course = str((g or {}).get("course") or p.get("course") or TAG_SOURCE)
            probe = {"subject": subject, "course": course, "name": name,
                     "raw_score": seed}
            meta = {
                "id": kp_id, "name": name, "subject": subject, "course": course,
                "domain": core.domain_of(subject, course),
                "transferable": core.facet_of(probe, "transferable"),
                "context": core.facet_of(probe, "context"),
                "importance": float(p.get("importance")
                                    or (g or {}).get("importance") or 0.6),
                "profile": str(p.get("profile") or (g or {}).get("profile")
                               or "foundation"),
                "prior_exposure": "high",
                "raw_score": seed, "current_score": seed, "peak_score": seed,
                "status": core.judge_status(seed, seed, seed)[0],
                "last_verified_at": core.TODAY.isoformat(),
                "origin": "inferred", "rejected": False, "evidence_ids": [],
                "tags": [strength, TAG_SOURCE],
            }
            body = (f"# {name}\n\n> 由联网检索推断（{strength}），未经确认。\n"
                    f"> 依据：{reason or '—'}\n> 来源：{url or '—'}\n")
            path = core.point_path(os.path.join(udir, "points"), name, subject)
        else:
            meta["raw_score"] = max(float(meta.get("raw_score", 0) or 0), seed)
            meta["current_score"] = meta["raw_score"]
            meta["peak_score"] = max(float(meta.get("peak_score", 0) or 0),
                                     meta["raw_score"])
            meta["last_verified_at"] = core.TODAY.isoformat()
            meta["origin"] = "inferred"
            meta["status"] = core.judge_status(
                meta["raw_score"], meta["raw_score"], meta["peak_score"])[0]
            tags = meta.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            for t in (strength, TAG_SOURCE):
                if t not in tags:
                    tags.append(t)
            meta["tags"] = tags

        ev_id = write_evidence(udir, meta["id"], strength,
                              f"{reason}｜匹配方式：{how or '新建'}"
                              + (f"｜{p.get('course')}" if p.get("course") else ""),
                              url)
        ev_ids = meta.get("evidence_ids") or []
        if isinstance(ev_ids, str):
            ev_ids = []
        ev_ids.append(ev_id)
        meta["evidence_ids"] = ev_ids
        core.write_md(path, meta, body)
        added_ev += 1
        (scored if how else created).append(f"{target}　{strength}")
        # 落盘后回填索引：同一次运行里出现重名条目时才能复用而不是重复建条
        index[target] = (path, meta, body)

    # 输出：改动摘要 + 给用户的批量确认话术
    out = []
    out.append(f"联网扩展 · 用户 {user_id}　来源 {len(sources)} 条，"
               f"检索知识点 {len(points)} 条{'（试运行，未落盘）' if dry_run else ''}")
    out.append(f"命中骨架并赋分 {len(scored)} 条；新建骨架外条目 {len(created)} 条；"
              f"跳过 {len(skipped)} 条"
              + (f"；写入证据 {added_ev} 条" if not dry_run else ""))
    if scored:
        out.append("\n命中骨架（赋分）：")
        for s in scored[:20]:
            out.append(f"  · {s}")
        if len(scored) > 20:
            out.append(f"  … 其余 {len(scored) - 20} 条")
    if created:
        out.append("\n骨架外新增：")
        for s in created[:20]:
            out.append(f"  · {s}")
    if skipped:
        out.append("\n跳过：")
        for s in skipped[:10]:
            out.append(f"  · {s}")
    if sources:
        out.append("\n来源清单（可追溯依据）：")
        for s in sources:
            out.append(f"  · {s.get('title', '')}　{s.get('url', '')}")
    out.append("\n【向用户批量确认】"
               "联网检索出上述知识点并已标为推断（未经确认）。"
               "把握较高的有："
               + "、".join(x.split("　")[0] for x in scored[:5]) + "。"
               "有标错的随时说，我会改成 rejected，不再参与计算；"
               "漏掉的方向也可以告诉我，我再检索补一遍。")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--input", required=True, help="检索结果 JSON 路径")
    p.add_argument("--dry-run", action="store_true", help="只打印计划不落盘")
    p.add_argument("--force", action="store_true",
                   help="对已有分数的知识点也刷新（只升不降）")
    a = p.parse_args()
    print(expand(a.user, a.input, a.dry_run, a.force))


if __name__ == "__main__":
    main()
