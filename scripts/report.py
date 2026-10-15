#!/usr/bin/env python3
"""生成知识分布报告（L0 概览 + 遗忘清单 + 盲区提示）。

这是给用户看的那一层：底层存连续分，报告只呈现等级与概览。

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
        })
        pts.append(meta)
    return pts


def bar(pct, width=BAR_WIDTH):
    n = int(round(pct / 100 * width))
    return FILLED * n + EMPTY * (width - n)


def subject_stats(pts):
    """学科聚合：加权平均，未触及计入分母。"""
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
    # 「其他」沉底，其余按掌握度降序
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
    depth = collections.Counter(
        p["_subject"] for p in pts if p["_raw"] > 0)
    bs = [p for p in pts if p["_raw"] <= 0 and p["_importance"] >= 1.0]
    bs.sort(key=lambda p: (-depth.get(p["_subject"], 0), -p["_importance"]))
    return bs[:top]


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


def build_report(user_id, pts, subject=None):
    """生成 Markdown 报告全文。"""
    L = []
    L.append(f"# 知识分布报告 · {user_id}")
    L.append("")
    L.append(f"> 生成于 {core.TODAY.isoformat()}"
             f"{'　范围：' + subject if subject else ''}"
             f"　覆盖 {len(pts)} 个知识点")
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
    tw = sum(p["_importance"] for p in pts)
    overall = sum(p["_current"] * p["_importance"] for p in pts) / tw
    tp = [p for p in pts if p["_raw"] > 0]
    t_score = (sum(p["_current"] * p["_importance"] for p in tp) /
               sum(p["_importance"] for p in tp)) if tp else 0
    L.append("## 一、总体概览")
    L.append("")
    L.append(f"- 已触及 **{touched}** / 共 {len(pts)} 个知识点"
             f"（{touched/len(pts)*100:.0f}%）")
    L.append(f"- 已触及部分平均掌握度 **{t_score:.0f}**"
             f"　（全库含未触及：**{overall:.0f}**）")
    L.append(f"- 正在生疏 **{sum(1 for p in pts if p['_status']=='rusty')}** 个")
    L.append("")
    L.append("> 全库均值把未触及项计入分母，会显著偏低；"
             "看真实水平请参照「已触及部分」。")
    L.append("")

    # 二、学科分布
    L.append("## 二、学科分布")
    L.append("")
    L.append("| 学科 | 掌握度 | 条形 | 已触及/总数 |")
    L.append("|---|---:|---|---|")
    for s in subject_stats(pts):
        L.append(f"| {s['subject']} | {s['score']:.0f}% | "
                 f"`{bar(s['score'])}` | {s['touched']}/{s['n']} |")
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

    # 六、近期动态
    ra = recent_activity(pts)
    L.append("## 六、近期动态（近 30 天）")
    L.append("")
    if ra:
        for p in ra:
            L.append(f"- {p.get('last_verified_at')}　{p.get('name')}"
                     f"　{core.LEVEL_LABEL.get(p['_base'], p['_base'])}")
    else:
        L.append("近 30 天没有新的验证记录。")
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
    t_score = (sum(p["_current"] * p["_importance"] for p in tp) /
               sum(p["_importance"] for p in tp)) if tp else 0
    print(f"知识分布 · {user_id}　共 {len(pts)} 个知识点"
          f"　已触及 {touched}　已触及均值 {t_score:.0f}")
    print()
    print("学科分布：")
    for s in subject_stats(pts):
        print(f"  {s['subject']:<12} {bar(s['score'])} "
              f"{s['score']:>3.0f}%  ({s['touched']}/{s['n']})")
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
