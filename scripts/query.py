#!/usr/bin/env python3
"""提问时查询档案：抽知识点 → 返回讲解深度建议 + Playbook + 画像。

这是本系统最核心的调用点。用法：
    python3 query.py --user u001 --q "红黑树和 AVL 树怎么选"
"""
import os
import re
import glob
import math
import argparse
import core
import link

# 讲解深度建议
ADVICE = {
    "untouched": "当全新知识讲，完整铺垫背景与动机",
    "aware": "补一层背景再进主题，先说清它解决什么问题",
    "understood": "默认知道原理，重点讲怎么用、有什么坑",
    "applicable": "默认你会用，直接进深水区与边界情况",
    "proficient": "只讲增量与例外，可反过来请用户补充",
    "rusty": "先一句唤醒（你以前在 XX 场景深入过），再展开",
}


# 名字里的连接词：切开之后每一块都能单独去问句里找
SPLIT_RE = re.compile(r"[与和及的、，,/／|｜·：:；;]+")
BRACKET_RE = re.compile(r"[（(][^）)]*[）)]")     # 括号里是别称/说明，不参与计分
NORM_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")

PARTIAL = 0.35   # 词块只中一部分时给的分：挡住「数据解读」靠「数据」压过「索引与 B+ 树」


def _norm(s):
    """只留中英文数字，去掉空格与标点——问句和名字用同一套口径比。"""
    return NORM_RE.sub("", str(s).lower())


def _parts(name):
    """把名字切成能独立命中的词块；括号里的别称不重复计分。"""
    base = BRACKET_RE.sub(" ", str(name))
    return [p for p in (_norm(x) for x in SPLIT_RE.split(base)) if len(p) >= 2]


def _lcs(a, b):
    """最长公共子串长度。名字都短，直接 DP，不做花活。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def score(name, question):
    """知识点名与问句的匹配度 0–1。

    为什么不用「2-gram 重合数 ÷ 名字长度」：那个算法**单方面惩罚长名字**。
    问「定积分怎么算」时，「不定积分」3 个 gram 中 2 个命中得 0.67，
    而正确答案「定积分与微积分基本定理」9 个 gram 中同样 2 个命中只得 0.22——
    名字越长越吃亏，等于越准确的条目排名越靠后。

    现在的做法是把名字切成**可独立命中的词块**（按「与/和/、/」等切开），
    整块出现在问句里才算满命中；只中一部分按比例给分，且打折。
    连接词不参与计分，所以「索引与 B+ 树」不会因为多了个「与」而被稀释。
    """
    nq = _norm(question)
    parts = _parts(name)
    if not parts or not nq:
        return 0.0
    num = den = 0.0
    for p in parts:
        w = math.sqrt(len(p))          # 长词块更有辨识度，但不按长度线性放大
        den += w
        if p in nq:
            num += w
        else:
            num += w * PARTIAL * (_lcs(p, nq) / len(p))
    return num / den if den else 0.0


STRONG = 0.4   # 名称强命中阈值
WEAK = 0.2     # 弱命中：只在强命中为空时才用


def match_points(udir, question):
    """三级匹配：名称强命中 → 名称弱命中 Top3 → 课程兜底。

    宁可少给也不要乱给：课程兜底只返回与问句确实有重叠的知识点，
    避免问「数据库索引」时把整个数据库课程都端上来。
    """
    strong, weak, by_course = [], [], {}
    # 走索引而不是逐条 read_md：500 条就是 500 次 open，本机 12 秒；
    # 索引有落盘缓存，热起来只要 0.1 秒
    for path, meta, _body in core.index_points(udir)["items"]:
        if meta.get("rejected"):
            continue
        name = str(meta.get("name", ""))
        if not name:
            continue
        s = score(name, question)
        if s >= STRONG:
            strong.append((path, meta, s))
        elif s >= WEAK:
            # 弱命中：词块只中了一部分（问「消息传递」时「消息队列」落到这里，
            # 不会挤掉强命中，但强命中为空时还能给个方向）
            weak.append((path, meta, s))
        if float(meta.get("raw_score", 0) or 0) > 0:
            by_course.setdefault(str(meta.get("course", "")), []).append(
                (path, meta, s))

    # 同名次时，已掌握的优先——查询的目的是判断"该怎么讲"，
    # 未触及的知识点（raw=0）信息量低，不该挤占已掌握项的位置
    def rank(x):
        return (-x[2], -float(x[1].get("raw_score", 0) or 0))

    if strong:
        return [(p, m) for p, m, _ in sorted(strong, key=rank)]

    if weak:
        return [(p, m) for p, m, _ in sorted(weak, key=rank)[:3]]

    # 课程兜底：只取与问句有重叠的知识点，没有退化为该课程已掌握的 Top3
    out = []
    for course, items in by_course.items():
        if not course or score(course, question) < WEAK:
            continue
        ranked = sorted(items, key=rank)
        picked = [x for x in ranked if x[2] > 0][:3] or ranked[:3]
        for p, m, _ in picked:
            m["_via_course"] = True
            out.append((p, m))
    return out


def match_playbooks(udir, question):
    out = []
    for path in glob.glob(os.path.join(udir, "experience", "playbooks", "*.md")):
        meta, body = core.read_md(path)
        when = str(meta.get("applicable_when", ""))
        tags = meta.get("capability_tags") or []
        if when and any(len(t) >= 2 and t in question for t in when.split()):
            out.append(meta)
        elif any(str(t) in question for t in tags):
            out.append(meta)
    return out


def load_features(udir):
    feats = []
    for path in glob.glob(os.path.join(udir, "features", "*.md")):
        meta, _ = core.read_md(path)
        if meta.get("confirmed_by_user") in (False, "false"):
            continue
        feats.append(meta)
    return sorted(feats, key=lambda m: -float(m.get("confidence", 0) or 0))


def related_names(points):
    """命中知识点的横向关联（去重、排除已命中的）。"""
    hit = {str(m.get("name")) for _p, m in points}
    out = []
    for _p, m in points:
        for r in (m.get("related") or []):
            r = str(r)
            if r not in hit and r not in out:
                out.append(r)
    return out


def skills_for(udir, points, question):
    """哪些技能用到了这些知识点，或技能名直接命中问题。

    技能分是**行为证据**得出的，所以这里只报熟练度，不报"懂不懂"。
    """
    names = {str(m.get("name")) for _p, m in points}
    out = []
    for _p, m, _b in core.index_skills(udir)["items"]:
        reqs = m.get("requires") or []
        if isinstance(reqs, str):
            reqs = [reqs]
        sname = str(m.get("name", ""))
        if (set(map(str, reqs)) & names) or (sname and sname in question):
            out.append((sname, float(m.get("level", 0) or 0),
                        str(m.get("cluster", ""))))
    return sorted(out, key=lambda x: -x[1])[:5]


def query(user_id, question):
    udir = core.user_dir(user_id)
    points = match_points(udir, question)
    print(f"问题：{question}\n")
    print("=" * 50)

    if not points:
        print("\n① 知识点：库中没有触及的记录，按全新知识处理。")
    else:
        print(f"\n① 触及 {len(points)} 个知识点：")
        for path, meta in points:
            raw = float(meta.get("raw_score", 0))
            cur = float(meta.get("current_score", raw))
            peak = float(meta.get("peak_score", raw))
            status, base = core.judge_status(raw, cur, peak)
            label = core.LEVEL_LABEL.get(base, base)
            tag = "（已生疏）" if status == "rusty" else ""
            via = "　[经课程命中]" if meta.get("_via_course") else ""
            seen = str(meta.get("last_verified_at") or "").strip()
            when = f"上次接触 {seen}" if seen else "尚无接触记录"
            print(f"   · {meta.get('name')}：{label}{tag} "
                  f"current={cur:.0f} {when}{via}")
            print(f"     → {ADVICE[status]}")

    pbs = match_playbooks(udir, question)
    print(f"\n② 经验 Playbook：{'命中 ' + str(len(pbs)) + ' 条' if pbs else '无'}")
    for pb in pbs:
        print(f"   · {pb.get('name')}（适用：{pb.get('applicable_when')}）")

    feats = load_features(udir)
    print(f"\n③ 行为画像：{len(feats)} 条已确认特征")
    for f in feats[:3]:
        print(f"   · {f.get('feature')}：{f.get('value')}")

    # 前置：讲某条之前先看它依赖什么，未触及就先补，别硬讲
    pre_lines = []
    for _p, m in points:
        pre_lines += link.format_prereq(udir, str(m.get("name")))
    # 无论如何都打这一行：打印是给人看的，编号缺一段会让人以为漏了内容
    print(f"\n④ 前置：{'无（这些条目没有登记前置）' if not pre_lines else ''}")
    for ln in pre_lines:
        print("   " + ln if not ln.startswith("   ") else ln)

    rel = related_names(points)
    print(f"\n⑤ 横向关联：{'命中 ' + str(len(rel)) + ' 条' if rel else '无'}")
    for r in rel[:6]:
        print(f"   · {r}")
    if rel:
        print("   （这些不是同学科的邻居，是你在自己的经历里连出来的）")

    sks = skills_for(udir, points, question)
    print(f"\n⑥ 相关技能：{'命中 ' + str(len(sks)) + ' 个' if sks else '无'}")
    for name, level, cluster in sks:
        print(f"   · {name}（{cluster}）熟练度 {level:.0f}"
              "　—— 技能分只来自做过的事，不代表原理懂多少")

    print("\n⑦ 建议：回答后写入 questions/ 日志；"
          "若暴露遗忘，记一条负向证据。"
          "\n   本次若同时点亮了多个知识点，用一条多目标证据录入（ingest --target A --target B），"
          "\n   共现够了 link.py 会提出连边建议。")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--q", required=True)
    a = p.parse_args()
    query(a.user, a.q)


if __name__ == "__main__":
    main()
