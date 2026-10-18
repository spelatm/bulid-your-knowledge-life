#!/usr/bin/env python3
"""生成知识分布报告（L0 概览 + 广度×深度 + 遗忘清单 + 待验证清单）。

这是给用户看的那一层：底层存连续分，报告只呈现等级、概览与**折叠**。

原则 B：存储层保持完整（骨架全铺），聚合、折叠、涌现全部放本层解决。

用法：
    python3 report.py --user u001                  # 终端打印
    python3 report.py --user u001 --save           # 落盘到 users/u001/reports/
    python3 report.py --user u001 --subject 数学    # 只看某个学科
"""
import os
import glob
import argparse
import datetime
import collections
import core

# 重要度：核心 1.0 / 一般 0.6 / 边缘 0.3
IMPORTANCE_DEFAULT = 0.6
BAR_WIDTH = 20
FILLED, EMPTY = "█", "░"
UNCLASSIFIED = "未归类"


def importance_of(meta):
    """优先读 importance 字段；否则从 tags 中的星级推断。"""
    if "importance" in meta:
        return float(meta["importance"])
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    for t in tags:
        n = str(t).count("⭐") or str(t).count("*")
        if n >= 2:
            return 1.0
        if n == 1:
            return 0.6
    if "core" in [str(t).lower() for t in tags]:
        return 1.0
    return IMPORTANCE_DEFAULT


def load_points(udir, subject=None):
    """读取全部有效知识点，顺带完成衰减重算（不写回）。"""
    pts = []
    for path in glob.glob(os.path.join(udir, "points", "*.md")):
        meta, body = core.read_md(path)
        if meta.get("rejected"):
            continue
        if subject and str(meta.get("subject", "")) != subject:
            continue
        raw = float(meta.get("raw_score", 0) or 0)
        profile = meta.get("profile", "foundation")
        last = meta.get("last_verified_at")
        if isinstance(last, str) and last:
            last_d = datetime.date.fromisoformat(last)
        else:
            last_d = None
        current, delta = core.apply_decay(raw, last_d, profile)
        peak = max(float(meta.get("peak_score", 0) or 0), raw)
        status, base = core.judge_status(raw, current, peak)
        meta.update({
            "_raw": raw, "_current": current, "_peak": peak,
            "_status": status, "_base": base, "_delta": delta or 0,
            "_importance": importance_of(meta),
            "_subject": str(meta.get("subject") or "未分类"),
            "_domain": str(meta.get("domain") or "") or UNCLASSIFIED,
            "_prior": str(meta.get("prior_exposure") or "minimal"),
            "_path": path,
        })
        pts.append(meta)
    return pts


def bar(pct, width=BAR_WIDTH):
    n = int(round(pct / 100 * width))
    return FILLED * n + EMPTY * (width - n)


def weighted_mean(ps, key):
    tw = sum(p["_importance"] for p in ps)
    if not tw:
        return 0.0
    return sum(p[key] * p["_importance"] for p in ps) / tw


def domain_stats(pts):
    """按**域**聚合（取代旧的 9 学科平铺）。

    广度 = 已触及比例（铺了多远）；深度 = 已触及部分的平均掌握度（扎得多深）。
    """
    g = collections.defaultdict(list)
    for p in pts:
        g[p["_domain"]].append(p)
    out = []
    for name, ps in g.items():
        touched = [p for p in ps if p["_raw"] > 0]
        out.append({
            "domain": name, "n": len(ps), "touched": len(touched),
            "breadth": len(touched) / len(ps) * 100 if ps else 0.0,
            "depth": weighted_mean(touched, "_current"),
        })
    # 有记录的域在前（按触及数降序）→ 空域 → 未归类沉底
    return sorted(out, key=lambda x: (x["touched"] == 0,
                                      x["domain"] == UNCLASSIFIED,
                                      -x["touched"], -x["depth"]))


def shape_label(breadth, depth):
    """把 (广度, 深度) 说成一句人话。阈值是启发式的，只用于描述。

    入参必须与表格里**展示的取整值**一致，否则会出现
    「显示 40% 却判成窄」这种自相矛盾。
    """
    b, d = round(breadth), round(depth)
    if b < 20 and d < 20:
        return "起步"
    if b >= 40 and d >= 45:
        return "扎实"
    if b >= 40:
        return "广而浅"
    if d >= 45:
        return "窄而深"
    return "在铺开"


def subject_stats(pts):
    """学科聚合（保留给 --subject 与终端摘要用）。"""
    agg = collections.defaultdict(lambda: {"w": 0.0, "sum": 0.0, "n": 0,
                                           "touched": 0})
    for p in pts:
        a = agg[p["_subject"]]
        w = p["_importance"]
        a["w"] += w
        a["sum"] += p["_current"] * w
        a["n"] += 1
        if p["_raw"] > 0:
            a["touched"] += 1
    out = []
    for name, a in agg.items():
        score = (a["sum"] / a["w"]) if a["w"] else 0
        out.append({"subject": name, "score": score, "n": a["n"],
                    "touched": a["touched"]})
    return sorted(out, key=lambda x: (x["subject"] == "其他", -x["score"]))


def level_dist(pts):
    d = collections.Counter(p["_base"] for p in pts)
    order = ["proficient", "applicable", "understood", "aware", "untouched"]
    return [(k, d.get(k, 0)) for k in order]


def rusty_list(pts, top=10):
    rs = [p for p in pts if p["_status"] == "rusty"]
    return sorted(rs, key=lambda p: p["_current"])[:top]


def blind_spots(pts, top=10):
    """核心但未触及 = 真盲区。

    排序原则：优先显示「你已有积累的学科里」的核心盲区——
    数学的核心知识点没学，对前端不重要；计算机科学里的才是真缺口。
    """
    depth = collections.Counter(p["_subject"] for p in pts if p["_raw"] > 0)
    bs = [p for p in pts if p["_raw"] <= 0 and p["_importance"] >= 1.0]
    bs.sort(key=lambda p: (-depth.get(p["_subject"], 0), -p["_importance"]))
    return bs[:top]


def to_verify(pts, per_subject=3):
    """待验证清单：先验说「大概接触过」，但档案里完全没有记录。

    只取 `medium` 档——即**同学科已有积累、这条却空缺**。
    `low` 档（仅同域有触及）指向性太弱：一个计算机学生并不因为
    学过数学，就大概接触过整个「人文与艺术」域，列出来只是噪声。
    先验**不是分数**，它只决定排序。详见 design/…方案.md §7.2。
    """
    cand = [p for p in pts if p["_raw"] <= 0 and p["_prior"] == "medium"]
    if not cand:
        return []
    g = collections.defaultdict(list)
    for p in cand:
        g[p["_subject"]].append(p)
    out = []
    for subj, ps in sorted(g.items(), key=lambda kv: -len(kv[1])):
        by_course = collections.defaultdict(list)
        for p in ps:
            by_course[str(p.get("course", "") or "未分组")].append(p)
        top = sorted(by_course.items(), key=lambda kv: -len(kv[1]))[:per_subject]
        out.append({"subject": subj, "n": len(ps),
                    "courses": [f"{c}（{len(v)}）" for c, v in top]})
    return out


def unconfirmed(pts, top=12):
    """有分、但来源是推断且未经确认——展示时必须与实测分离。"""
    uc = [p for p in pts if p["_raw"] > 0 and str(p.get("origin")) == "inferred"]
    g = collections.defaultdict(list)
    for p in uc:
        g[p["_subject"]].append(p)
    out = []
    for subj, ps in sorted(g.items(), key=lambda kv: -len(kv[1]))[:top]:
        out.append({"subject": subj, "n": len(ps)})
    return out, len(uc)


def recent_activity(pts, days=30):
    out = []
    for p in pts:
        last = p.get("last_verified_at")
        if isinstance(last, str) and last:
            try:
                d = datetime.date.fromisoformat(last)
                if (core.TODAY - d).days <= days:
                    out.append(p)
            except ValueError:
                pass
    return sorted(out, key=lambda p: str(p.get("last_verified_at")),
                  reverse=True)[:10]


def skill_rows(udir, pts):
    """技能：熟练度、知识均分、gap。零熟练度的按簇折叠（原则 B）。"""
    import skill as skill_mod
    pidx = {"by_name": {str(p.get("name")): ("", p, "") for p in pts}}
    idx = core.index_skills(udir)
    live, folded = [], collections.defaultdict(list)
    for _p, m, _b in idx["items"]:
        lvl = float(m.get("level", 0) or 0)
        row = {"name": m.get("name"), "cluster": m.get("cluster", "未分簇"),
               "kind": m.get("kind"), "level": lvl}
        row["gap"], row["mean"], row["missing"] = skill_mod.gap_of(udir, m, pidx)
        row["verdict"] = skill_mod.verdict(row["gap"])
        (live if lvl > 0 else folded[row["cluster"]]).append(row)
    return live, folded


def edge_stats(udir, pts):
    """横向边统计：总数 + 跨域条数（跨域边才是这套系统的价值所在）。"""
    pairs, dom = set(), {}
    for p in pts:
        for name in (p.get("related") or []):
            pairs.add(tuple(sorted((str(p.get("name")), str(name)))))
    for p in pts:
        dom[str(p.get("name"))] = str(p.get("domain", "") or "")
    cross = sum(1 for a, b in pairs
                if dom.get(a) and dom.get(b) and dom.get(a) != dom.get(b))
    return len(pairs), cross


def build_report(user_id, pts, subject=None):
    """生成 Markdown 报告全文。"""
    L = []
    L.append(f"# 知识分布报告 · {user_id}")
    L.append("")
    L.append(f"> 生成于 {core.TODAY.isoformat()}"
             f"{'　范围：' + subject if subject else ''}"
             f"　覆盖 {len(pts)} 个知识点")
    L.append(">")
    L.append("> 这是**展示层**：所有分数由证据层聚合得出，本文件不单独维护数据。")
    L.append("")

    if not pts:
        L.append("还没有任何知识点记录。先跑一次冷启动：")
        L.append("")
        L.append("```")
        L.append('python3 scripts/init_profile.py --user <id> '
                 '--edu "" --job "" --region ""')
        L.append("```")
        return "\n".join(L)

    # 一、总体
    touched = sum(1 for p in pts if p["_raw"] > 0)
    tp = [p for p in pts if p["_raw"] > 0]
    t_score = weighted_mean(tp, "_current")
    overall = weighted_mean(pts, "_current")
    _, n_uc = unconfirmed(pts)
    L.append("## 一、总体概览")
    L.append("")
    L.append(f"- 已触及 **{touched}** / 共 {len(pts)} 个知识点"
             f"（{touched/len(pts)*100:.0f}%）")
    L.append(f"- 已触及部分平均掌握度 **{t_score:.0f}**"
             f"　（全库含未触及：**{overall:.0f}**）")
    L.append(f"- 正在生疏 **{sum(1 for p in pts if p['_status']=='rusty')}** 个"
             f"　｜　待确认的推断分 **{n_uc}** 条（见第六节）")
    L.append("")
    L.append("> 全库均值把未触及项计入分母，会显著偏低；"
             "看真实水平请参照「已触及部分」。")
    L.append("")

    # 二、域分布（折叠）+ 广度×深度
    rows = domain_stats(pts)
    live = [r for r in rows if r["touched"] > 0 and r["domain"] != UNCLASSIFIED]
    empty = [r for r in rows if r["touched"] == 0 and r["domain"] != UNCLASSIFIED]
    other = [r for r in rows if r["domain"] == UNCLASSIFIED]
    L.append("## 二、域分布（广度 × 深度）")
    L.append("")
    L.append("**广度**＝该域里已触及的比例（铺了多远）　"
             "**深度**＝已触及部分的平均掌握度（扎得多深）")
    L.append("")
    L.append("| 域 | 深度 | 广度 | 分布（深度） | 已触及/总数 | 形状 |")
    L.append("|---|---:|---:|---|---|---|")
    for r in list(live) + list(other):
        shape = ("—" if r["domain"] == UNCLASSIFIED
                 else shape_label(r["breadth"], r["depth"]))
        L.append(f"| {r['domain']} | {r['depth']:.0f}% | {r['breadth']:.0f}% | "
                 f"`{bar(r['depth'])}` | {r['touched']}/{r['n']} | {shape} |")
    L.append("")
    if empty:
        # 域名本身可能含顿号（「工程、制造与建造」），所以逐个加引号再连排，
        # 否则会读成比实际更多的域
        names = "".join(f"「{r['domain']}」" for r in empty)
        total = sum(r["n"] for r in empty)
        L.append(f"> **另有 {len(empty)} 个域尚无任何记录**（共 {total} 个知识点，"
                 f"骨架已铺、随时可记）：")
        L.append(f"> {names}")
        L.append("")
        L.append("> 它们不是「没收录」，而是「你还没在那儿留下痕迹」——"
                 "这正是骨架全铺的意义：位置一直都在。")
        L.append("")

    # 三、掌握度分层
    L.append("## 三、掌握度分层")
    L.append("")
    L.append("| 层级 | 数量 | 占比 |")
    L.append("|---|---:|---:|")
    for k, v in level_dist(pts):
        L.append(f"| {core.LEVEL_LABEL.get(k, k)} | {v} | "
                 f"{v/len(pts)*100:.0f}% |")
    L.append("")

    # 四、遗忘清单
    rs = rusty_list(pts)
    L.append("## 四、正在生疏（遗忘清单）")
    L.append("")
    if rs:
        L.append("| 知识点 | 学科 | 曾达 | 现在 | 未接触 |")
        L.append("|---|---:|---:|---:|---:|")
        for p in rs:
            L.append(f"| {p.get('name')} | {p['_subject']} | "
                     f"{p['_peak']:.0f} | {p['_current']:.0f} | "
                     f"{p['_delta']} 天 |")
        L.append("")
        L.append("> 这些不是「不会」，而是「曾经会、现在可能废了」。")
        L.append("> 提问触及它们时，会先给一句唤醒再展开。")
    else:
        L.append("暂无生疏知识点。")
    L.append("")

    # 五、盲区
    bs = blind_spots(pts)
    L.append("## 五、盲区提示")
    L.append("")
    if bs:
        L.append("核心知识点、但完全未触及的：")
        L.append("")
        for p in bs:
            L.append(f"- {p.get('name')}"
                     f"（{p['_subject']} / {p.get('course','')}）")
    else:
        L.append("没有未触及的核心知识点。")
    L.append("")

    # 六、待验证与待确认
    L.append("## 六、待验证与待确认")
    L.append("")
    L.append("> **先验不是分数。** 下面两节都是**猜测**，"
             "只用来告诉你「哪里可能有个位置」，不参与任何计算。")
    L.append("")
    tv = to_verify(pts)
    L.append("### 6.1 待验证（按背景大概接触过，但档案里没有记录）")
    L.append("")
    if tv:
        L.append("| 学科 | 未记录 | 集中在哪几门 |")
        L.append("|---|---:|---|")
        for r in tv:
            courses = "、".join(r["courses"]) if r["courses"] else "—"
            L.append(f"| {r['subject']} | {r['n']} 条 | {courses} |")
        L.append("")
        L.append("有就说一声，我会记下来；确实没有，忽略即可。")
    else:
        L.append("暂无——档案与背景已基本对齐。")
    L.append("")
    uc_rows, uc_total = unconfirmed(pts)
    L.append("### 6.2 待你确认（推断分，非实测）")
    L.append("")
    if uc_rows:
        L.append(f"以下 **{uc_total}** 条的分数是**背景 / 联网推断**出来的，"
                 "未经你确认，**不计入真实水平**：")
        L.append("")
        for r in uc_rows:
            L.append(f"- {r['subject']}：{r['n']} 条")
        L.append("")
        L.append("标错的随时告诉我，标 `rejected` 后就不再参与计算。")
    else:
        L.append("没有未经确认的推断分。")
    L.append("")

    # 七、近期动态
    ra = recent_activity(pts)
    L.append("## 七、近期动态（近 30 天）")
    L.append("")
    if ra:
        for p in ra:
            L.append(f"- {p.get('last_verified_at')}　{p.get('name')}"
                     f"　{core.LEVEL_LABEL.get(p['_base'], p['_base'])}")
    else:
        L.append("近 30 天没有新的验证记录。")
    L.append("")

    # 八、技能与错位
    udir = core.user_dir(user_id)
    live, folded = skill_rows(udir, pts)
    n_edges, n_cross = edge_stats(udir, pts)
    n_skill = len(live) + sum(len(v) for v in folded.values())
    L.append("## 八、技能与错位")
    L.append("")
    L.append("> **知识分与技能分是两套独立计算**：知识分来自学习证据（读过、想过、"
             "推过），技能分来自行为证据（写过、做过、教过别人），**互不推导**。")
    L.append(">")
    L.append("> `gap = 技能熟练度 − 支撑它的知识点均分`：")
    L.append("> `+20` 以上＝手熟但原理淡了（该补原理）；`−20` 以下＝学过但没做过"
             "（该给练习）。这正是简历答不出、又最该知道的那件事。")
    L.append("")
    if n_skill:
        if live:
            L.append("| 技能 | 簇 | 熟练度 | 知识均分 | gap | 判读 | 该做什么 |")
            L.append("|---|---|---:|---:|---:|---|---|")
            for r in sorted(live, key=lambda x: -(x["gap"] or 0)):
                mean = "—" if r["mean"] is None else f"{r['mean']:.0f}"
                gap = "—" if r["gap"] is None else f"{r['gap']:+.0f}"
                L.append(f"| {r['name']} | {r['cluster']} | {r['level']:.0f} | "
                         f"{mean} | {gap} | {r['verdict'][0]} | "
                         f"{r['verdict'][1]} |")
            L.append("")
        if folded:
            names = "、".join(f"「{c}」{len(v)} 个" for c, v in
                             sorted(folded.items(), key=lambda kv: -len(kv[1])))
            L.append(f"> 另有 **{sum(len(v) for v in folded.values())}** 个技能"
                     f"尚无行为证据（熟练度 0，不占篇幅）：{names}")
            L.append("> 技能分不会因为「你大概会」而给分——没有做过的记录，就是 0。")
            L.append("")
    else:
        L.append("还没有技能实体。预置能力簇："
                 "`python3 scripts/skill.py --user <id> --seed`")
        L.append("")
    L.append(f"**关联网络**：{n_edges} 条横向边"
             f"（其中跨域 **{n_cross}** 条）。纵向边是学科给的，横向边是你自己长出来的；"
             "跨域的那几条是这份档案里最难被替代的部分。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*本报告由 L2 证据层聚合计算得出，不单独维护展示数据。*")
    return "\n".join(L)


def print_console(user_id, pts):
    """终端摘要，不落盘。"""
    if not pts:
        print("还没有知识点记录。")
        return
    touched = sum(1 for p in pts if p["_raw"] > 0)
    tp = [p for p in pts if p["_raw"] > 0]
    t_score = weighted_mean(tp, "_current")
    print(f"知识分布 · {user_id}　共 {len(pts)} 个知识点"
          f"　已触及 {touched}　已触及均值 {t_score:.0f}")
    print()
    print("域分布（广度 × 深度）：")
    for r in domain_stats(pts):
        if r["touched"] == 0:
            continue
        print(f"  {r['domain']:<12} 深 {r['depth']:>3.0f}%  "
              f"广 {r['breadth']:>3.0f}%  {bar(r['depth'], 12)}  "
              f"({r['touched']}/{r['n']})")
    hidden = [r for r in domain_stats(pts) if r["touched"] == 0]
    if hidden:
        print(f"  （另有 {len(hidden)} 个域尚无记录："
              f"{'、'.join('「' + r['domain'] + '」' for r in hidden)}）")
    print()
    print("掌握度分层：")
    for k, v in level_dist(pts):
        print(f"  {core.LEVEL_LABEL.get(k, k):<6} {bar(v/len(pts)*100, 12)} {v}")
    rs = rusty_list(pts)
    print()
    print(f"正在生疏：{len(rs)} 个")
    for p in rs[:5]:
        print(f"  · {p.get('name')}：{p['_peak']:.0f} → "
              f"{p['_current']:.0f}（{p['_delta']} 天未接触）")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--subject", default="")
    p.add_argument("--save", action="store_true", help="落盘为 markdown")
    a = p.parse_args()

    udir = core.user_dir(a.user)
    if not os.path.isdir(udir):
        print(f"用户 {a.user} 不存在，先跑 init_profile.py。")
        return
    pts = load_points(udir, a.subject or None)

    if a.save:
        text = build_report(a.user, pts, a.subject or None)
        outdir = os.path.join(udir, "reports")
        os.makedirs(outdir, exist_ok=True)
        name = (f"{core.TODAY.strftime('%Y%m%d')}-知识分布报告"
                f"{'-' + a.subject if a.subject else ''}.md")
        path = os.path.join(outdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"报告已写入：{os.path.relpath(path, core.ROOT)}")
    else:
        print_console(a.user, pts)


if __name__ == "__main__":
    main()
