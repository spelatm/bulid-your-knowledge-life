#!/usr/bin/env python3
"""冷启动：采集背景 → 套推断模板 → 铺知识点 → 生成本地档案。

用法：
    python3 init_profile.py --user u001 \
        --edu "计算机本科" --job "前端工程师 5年" --region "杭州"
"""
import os
import re
import glob
import argparse
import datetime
import collections
import core

# 推断强度 → raw 初值
STRENGTH_SCORE = {"strong": 50.0, "likely": 30.0, "possible": 20.0}

# 章节标题里不值得当关键词的通用词
KW_STOPWORDS = {"其他", "任何", "通用", "以上", "方向", "进阶", "类目", "基础"}


def parse_inference(file_path, keywords):
    """从映射文件中抽出命中关键词的知识点。

    极简实现：章节命中或**该行本身**命中关键词即算命中，
    提取行中的知识点名与强度标记。
    实际使用时应由智能体做语义匹配，这里提供可运行的骨架。
    """
    hits = {}
    if not os.path.exists(file_path) or not keywords:
        return hits
    with open(file_path, encoding="utf-8") as f:
        section = ""
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                section = line.lstrip("# ").strip()
                continue
            if not line.startswith("-"):
                continue
            # 命中条件：所在章节命中，或该行自身命中。
            # 后者让「- 人工智能 〔likely，研究生 strong〕」这类
            # 非标题行也能被关键词捞出来。
            if not any(k in section for k in keywords) and \
               not any(k in line for k in keywords):
                continue
            mm = re.search(r"〔(strong|likely|possible)", line)
            strength = mm.group(1) if mm else "likely"
            # 去掉强度标记，剩余形如 "课程 → 知识点A、知识点B"
            body = re.sub(r"[〔\[].*?[〕\]]", "", line).lstrip("- ").strip()
            if "→" in body:
                course, rest = body.split("→", 1)
                course = re.split(r"[（(]", course)[0].strip()
                names = [x.strip() for x in re.split(r"[、,，]", rest) if x.strip()]
            else:
                course = section
                names = [re.split(r"[（(]", body)[0].strip()]
            for n in names:
                if n:
                    hits[n] = (strength, course)
    return hits


def iter_headings(file_path):
    """取出推断文件里的全部章节标题。"""
    out = []
    if not os.path.exists(file_path):
        return out
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                out.append(line.lstrip("# ").strip())
    return out


def extract_keywords(user_text, file_path):
    """从**用户原话**里反向提炼关键词，用于匹配该推断文件的章节。

    旧实现取 user_text[:3]：用户填的是一整句话
    （"2026级燕山大学人工智能学院计算机技术专业研究生"）时，关键词退化成
    "202"，所有章节标题都匹配不上，整条背景推断静默失效、488 条骨架全 0 分。
    反过来做才对——先看文件里有哪些章节词，再看用户的哪段原话命中了它。

    关键词必须来自用户原话，所以不会像手工关键词表那样，
    凭一个泛化词推出用户根本没提过的东西（例：拿"教师"去匹配
    「教师/培训」章节，会给一个学生推出"教学设计与课堂管理"）。
    另外只保留**极大**片段：'工程师' 是 '前端工程师' 的子串，
    留着它会让"前端工程师"顺带命中「算法/AI 工程师」等无关章节。
    """
    if not user_text or user_text in ("未填", "未知", "-", "—"):
        return []
    cands = []
    for h in iter_headings(file_path):
        for seg in re.split(r"[（）()、，,/／·：:\s]+", h):
            seg = re.sub(r"(类|方向|进阶|类目)$", "", seg.strip())
            if len(seg) < 2 or seg in KW_STOPWORDS:
                continue
            if seg in user_text and seg not in cands:
                cands.append(seg)
    return [c for c in cands
            if not any(c != o and c in o for o in cands)]


def select_subjects(graph, hit_names, limit=4, min_hits=2):
    """按背景推断的命中数挑出最相关的学科（最多 limit 个）。

    graph/README.md 的设计是「初始化时按用户背景选 2–4 个学科铺开，
    其余折叠为学科名」；铺满 9 个学科会让报告里出现一整排 0% 的噪声行。
    命中数低于 min_hits 的学科不入选——只沾到 1 条的学科是噪声，
    它那一条会退回「其他」，等比铺开整个学科更干净。
    """
    cnt = collections.Counter()
    for g in graph:
        if g["name"] in hit_names:
            cnt[g["subject"]] += 1
    return [s for s, n in cnt.most_common(limit) if n >= min_hits]


TOKEN_SEP = r"[\s/／、，,：:·｜|]+"


def score_candidates(g, merged):
    """算出该骨架知识点的候选匹配：((排序键), 强度, 命中的推断名)。

    打分维度从高到低：精确 > 包含，包含再比
    ① 课程是否同源 ② 是否切在词边界 ③ 是否以 key 开头 ④ 重叠比例。
    「以 key 开头」这一维很关键：由课程行推导出的 key，通常对应以它开头的
    条目——否则"事务"会被名字更短的「分布式事务」抢走，而不是
    「事务与 ACID」。
    单字 key 只在**课程同源**时才允许匹配（"树"→「树与二叉树」），
    否则宁可留给用户手工确认，也不要乱点。
    """
    out = []
    names = [g["name"]] + list(g.get("aliases", []))
    gc = str(g.get("course", "") or "")
    for key, (strength, course) in merged.items():
        aff = 1 if (course and gc and (course in gc or gc in course)) else 0
        for c in names:
            if c == key:
                out.append(((4, aff, 1, 1, 1.0), strength, key))
                break
            if len(key) >= 2 and (key in c or c in key):
                tok = 1 if key in re.split(TOKEN_SEP, c) else 0
                pre = 1 if c.startswith(key) else 0
                ov = len(key) / max(len(key), len(c))
                out.append(((2, aff, tok, pre, ov), strength, key))
                break
            if len(key) == 1 and aff and c.startswith(key):
                out.append(((1, aff, 0, 1, 1.0 / max(1, len(c))), strength, key))
                break
    return out


def assign_hits(items, merged):
    """全局唯一分配：产出 {知识点名: (强度, 命中的推断名)}。

    逐条匹配有两个反向的毛病：太宽——短 key 会同时点亮多条骨架知识点
    （"逻辑"把「逻辑学」「命题逻辑与谓词逻辑」「逻辑回归」一起点亮，
    纯属分数污染）；太窄——单字 key 被长度门槛直接丢掉。
    所以先算出所有候选对并打分，再全局贪心分配：
    一个推断项只点亮一条知识点，一条知识点也只被一个推断项点亮。
    某个知识点被点亮后，它自己的其他等义写法（骨架名与别名）一并算作
    已消化，否则「异步」和「事件循环」——同一条的两个别名——
    只会有一个被吸收，另一个白白另建一条重复项。
    """
    pairs, index = [], {}
    for g in items:
        index[g["name"]] = g
        for sort_key, strength, key in score_candidates(g, merged):
            pairs.append((sort_key, g["name"], strength, key))
    pairs.sort(key=lambda x: x[0], reverse=True)
    got, used_keys = {}, set()
    for _, name, strength, key in pairs:
        if name in got or key in used_keys:
            continue
        got[name] = (strength, key)
        for k in [name] + list(index[name].get("aliases", [])):
            if k in merged:
                used_keys.add(k)
    return got


def consumed_keys(items, merged, hits):
    """算出「已消化的推断项」集合 = 被赋分的 key ∪ 同一条知识点的其他等义写法。

    少了后半部分就会出重复条目：「异步与事件循环」的别名是
    「事件循环、异步」，赋分只记下其中一个，另一个会被当成没命中，
    白白在「其他」里再建一条一模一样的。
    """
    used = {key for _, key in hits.values()}
    index = {g["name"]: g for g in items}
    for name in hits:
        g = index.get(name)
        if not g:
            continue
        for k in [name] + list(g.get("aliases", [])):
            if k in merged:
                used.add(k)
    return used


def build_profile(user_id, edu, job, region, subjects=None, keywords=None):
    """生成用户档案与推断知识点。"""
    udir = core.user_dir(user_id)
    for sub in ("points", "experience/projects", "experience/actions",
                "experience/artifacts", "experience/playbooks",
                "wisdom", "features", "questions", "evidence"):
        os.makedirs(os.path.join(udir, sub), exist_ok=True)

    # 采集背景（与已有档案合并，不覆盖 created_at）
    ppath = os.path.join(udir, "profile.md")
    old, _ = core.read_md(ppath) if os.path.exists(ppath) else ({}, "")
    has_points = bool(glob.glob(os.path.join(udir, "points", "*.md")))
    for k, v in (("education", edu), ("occupation", job), ("region", region)):
        if v and v != "未填":
            old[k] = v
    old.setdefault("user_id", user_id)
    old.setdefault("created_at", core.TODAY.isoformat())
    old["updated_at"] = core.TODAY.isoformat()
    complete = all(str(old.get(k, "")).strip() not in ("", "未填", "未知")
                   for k in ("education", "occupation", "region"))
    old["onboarding"] = "ready" if complete else "partial"
    core.write_md(
        ppath, old,
        "# {u} 的能力档案\n\n- 学历：{e}\n- 职业：{j}\n- 区域：{r}\n".format(
            u=user_id, e=old.get("education", ""),
            j=old.get("occupation", ""), r=old.get("region", "")),
    )

    # 三条推断路径。关键词默认从用户原话里反向提取（见 extract_keywords），
    # 需要时可显式传入语义关键词覆盖。
    edu_path = os.path.join(core.ROOT, "inference", "学历映射.md")
    job_path = os.path.join(core.ROOT, "inference", "职业映射.md")
    reg_path = os.path.join(core.ROOT, "inference", "区域映射.md")
    keywords = keywords or {}
    edu_kw = keywords.get("edu") or extract_keywords(edu, edu_path)
    job_kw = keywords.get("job") or extract_keywords(job, job_path)
    reg_kw = keywords.get("region") or extract_keywords(region, reg_path)

    edu_hits = parse_inference(edu_path, edu_kw)
    job_hits = parse_inference(job_path, job_kw)
    region_hits = parse_inference(reg_path, reg_kw)

    merged = {}
    for src in (region_hits, job_hits, edu_hits):   # 后者优先级更高
        for k, v in src.items():
            rank = {"possible": 0, "likely": 1, "strong": 2}
            if k not in merged or rank[v[0]] > rank[merged[k][0]]:
                merged[k] = v

    # 推断透明：把实际用的关键词与命中数打出来，便于追溯"为什么会得出这个结论"
    print(f"背景关键词 —— 学历：{edu_kw or '（无）'} → {len(edu_hits)} 条；"
          f"职业：{job_kw or '（无）'} → {len(job_hits)} 条；"
          f"区域：{reg_kw or '（无）'} → {len(region_hits)} 条")
    if not merged:
        print("\n⚠️ 静态映射表零命中：背景推断为空，488 条骨架会全部是 0 分。")
        print("   静态模板覆盖不了这个背景，请走 SKILL.md §0.7「联网扩展档案」：")
        print("   联网检索该背景对应的知识体系，产出 inferences.json 后执行")
        print("   python3 scripts/expand_profile.py --user <id> --input inferences.json")
        print("   （也可用 --edu-kw/--job-kw/--region-kw 手工指定语义关键词重试）")

    # 背景指向的学科集合——用于给新条目定先验档位（见下方 save）
    picked_set = set(subjects or [])

    # 推断来源写进 tags，供追溯
    def source_of(name):
        if name in edu_hits:
            return "学历推断"
        if name in job_hits:
            return "职业推断"
        return "区域推断"

    # 骨架匹配与全局分配见模块级 assign_hits() / score_candidates()



    def save(name, subject, course, importance, profile, strength,
             note="", source=""):
        pid = core.new_id("kp")
        scored = strength is not None
        raw = STRENGTH_SCORE[strength] if scored else 0.0
        body = f"# {name}\n"
        if scored:
            body += f"\n> 由背景推断（{strength}），未经确认。\n"
            if note:
                body += f"> {note}\n"
        probe = {"subject": subject, "course": course, "name": name,
                 "raw_score": raw}
        # 先验（永不参与算分）：有推断分 → high；无分但在背景指向的学科里
        # → medium（这正是报告里「待验证」清单的来源）
        prior = ("high" if scored
                 else ("medium" if subject in picked_set else "minimal"))
        core.write_md(
            core.point_path(os.path.join(udir, "points"), name, subject),
            {"id": pid, "name": name, "subject": subject, "course": course,
             "domain": core.domain_of(subject, course),
             "transferable": core.facet_of(probe, "transferable"),
             "context": core.facet_of(probe, "context"),
             "importance": importance, "profile": profile,
             "prior_exposure": prior,
             "raw_score": raw, "current_score": raw, "peak_score": raw,
             "status": core.judge_status(raw, raw, raw)[0],
             "last_verified_at": core.TODAY.isoformat() if scored else "",
             "origin": "inferred" if scored else "preset",
             "rejected": False, "evidence_ids": [],
             # 来源用**命中的推断名**去查，否则永远落到兜底值
             "tags": ([strength, source or source_of(name)] if scored else [])},
            body,
        )

    # 别名表：骨架名 → 别名。补充分支也要能用，否则补跑时别名匹配失效
    graph = core.parse_graph()
    alias_map = {g["name"]: g.get("aliases", []) for g in graph}

    if has_points:
        # 补充模式：档案已存在，只给「未触及」的知识点赋推断分，
        # 已有分数的不动——避免抹掉已积累的证据。
        existing = []
        for path in glob.glob(os.path.join(udir, "points", "*.md")):
            m, body = core.read_md(path)
            existing.append({"path": path, "meta": m, "body": body})
        got = assign_hits([{"name": str(e["meta"].get("name", "")),
                            "aliases": alias_map.get(
                                str(e["meta"].get("name", "")), []),
                            "course": str(e["meta"].get("course", "") or "")}
                           for e in existing], merged)
        added = 0
        for e in existing:
            m, body = e["meta"], e["body"]
            if float(m.get("raw_score", 0) or 0) > 0:
                continue
            hit = got.get(str(m.get("name", "")))
            if not hit:
                continue
            strength, key = hit
            raw = STRENGTH_SCORE[strength]
            m.update({"raw_score": raw, "current_score": raw,
                      "peak_score": raw, "last_verified_at": core.TODAY.isoformat(),
                      "origin": "inferred",
                      "status": core.judge_status(raw, raw, raw)[0],
                      "tags": [strength, source_of(key)]})
            core.write_md(e["path"], m, body)
            added += 1

        # 补充模式下，用户已触及的学科即「背景指向」——新补进来的骨架条目
        # 按 medium 记先验，才会出现在报告的「待验证」清单里
        picked_set.update(str(e["meta"].get("subject", "")) for e in existing
                          if float(e["meta"].get("raw_score", 0) or 0) > 0)

        # 骨架会演进（新增课程/知识点），已有档案不该因此缺条、更不该
        # 与旧的「其他」条目并存。补齐缺失条目；别名已存在的视为已满足，
        # 用户明确否认（rejected）的不再复活。
        have, rejected = set(), set()
        for e in existing:
            n = str(e["meta"].get("name", ""))
            (rejected if e["meta"].get("rejected") else have).add(n)
        missing = []
        for g in graph:
            names = [g["name"]] + list(g.get("aliases", []))
            if any(n in have or n in rejected for n in names):
                continue
            missing.append(g)
            have.add(g["name"])
        for g in missing:
            save(g["name"], g["subject"], g["course"], g["importance"],
                 g["profile"], None)
        print(f"用户 {user_id} 已有档案，补充赋分 {added} 个知识点"
              f"（已掌握的不动）；按骨架补齐 {len(missing)} 条新条目。")
        return merged

    # 首次铺开：按背景推断选 2–4 个相关学科铺开（graph/README.md 的设计），
    # 未命中的保留 raw=0——它们才是盲区。
    hits = {}
    if subjects:
        picked = list(subjects)
    else:
        picked = select_subjects(graph, set(assign_hits(graph, merged)))
        if not picked:
            picked = sorted({g["subject"] for g in graph})
            print("⚠️ 背景推断无命中，退回铺开全部学科（报告噪声较大，"
                  "建议先走 §0.7 联网扩展）。")
    picked_set.update(picked)
    # 学科选定后再分配一次：否则推断项会被未铺开学科的知识点抢走，
    # 结果是它既不赋分、也不会进「其他」，静默丢失
    laid = [g for g in graph if g["subject"] in picked]
    hits = assign_hits(laid, merged)
    used = consumed_keys(laid, merged, hits)
    for g in laid:
        hit = hits.get(g["name"])
        save(g["name"], g["subject"], g["course"], g["importance"],
             g["profile"], hit[0] if hit else None,
             source=source_of(hit[1]) if hit else "")

    # 骨架外的推断项（如区域带来的行业认知）归入「其他」，来源写进 tags；
    # 顺带记下骨架里命名相近的条目，方便日后合并而不是长期并存两条
    created = []
    for name, (strength, course) in merged.items():
        if name in used:
            continue
        near = [g["name"] for g in graph
                if len(name) >= 2 and (name in g["name"] or g["name"] in name)][:4]
        save(name, "其他", course, 0.6, "foundation", strength,
             note=("骨架里相近的条目： " + "、".join(near)
                   + "　确认后应合并成一条，不要长期并存。" if near else ""))
        created.append(name)

    n_touch = sum(1 for _ in glob.glob(os.path.join(udir, "points", "*.md")))
    strong = [k for k, v in merged.items() if v[0] == "strong"]
    print(f"已为用户 {user_id} 铺开 {len(laid)} 个知识点"
          f"（学科：{'、'.join(picked)}）：命中骨架赋分 {len(hits)} 个，"
          f"骨架外新建 {len(created)} 个。")
    print(f"把握较高的（{len(strong)} 个）：{'、'.join(strong[:6])}"
          f"{'…' if len(strong) > 6 else ''}")
    print(f"\n已触及 {len(hits) + len(created)} / {n_touch}，"
          f"其余为盲区（会在报告中体现）。")
    print("请向用户批量确认：有标错的随时告知，我会改。")
    return merged


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--edu", default="")
    p.add_argument("--job", default="")
    p.add_argument("--region", default="")
    p.add_argument("--subjects", default="",
                   help="限定铺开的学科，逗号分隔；默认按背景推断自动选 2–4 个")
    p.add_argument("--edu-kw", default="", help="手工指定学历关键词，逗号分隔")
    p.add_argument("--job-kw", default="", help="手工指定职业关键词，逗号分隔")
    p.add_argument("--region-kw", default="", help="手工指定区域关键词，逗号分隔")
    p.add_argument("--skip-onboarding", action="store_true",
                   help="用户跳过背景采集：铺骨架全部 0 分")
    a = p.parse_args()
    subs = [s.strip() for s in a.subjects.split(",") if s.strip()] or None

    def kws(raw):
        return [s.strip() for s in raw.split(",") if s.strip()] or None

    if a.skip_onboarding:
        a.edu = a.edu or "未填"
        a.job = a.job or "未填"
        a.region = a.region or "未填"
    build_profile(a.user, a.edu, a.job, a.region, subs,
                  {"edu": kws(a.edu_kw), "job": kws(a.job_kw),
                   "region": kws(a.region_kw)})


if __name__ == "__main__":
    main()
