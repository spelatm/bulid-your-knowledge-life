#!/usr/bin/env python3
"""提问时查询档案：抽知识点 → 返回讲解深度建议 + Playbook + 画像。

这是本系统最核心的调用点。用法：
    python3 query.py --user u001 --q "红黑树和 AVL 树怎么选"
"""
import os
import re
import glob
import argparse
import core

# 讲解深度建议
ADVICE = {
    "untouched": "当全新知识讲，完整铺垫背景与动机",
    "aware": "补一层背景再进主题，先说清它解决什么问题",
    "understood": "默认知道原理，重点讲怎么用、有什么坑",
    "applicable": "默认你会用，直接进深水区与边界情况",
    "proficient": "只讲增量与例外，可反过来请用户补充",
    "rusty": "先一句唤醒（你以前在 XX 场景深入过），再展开",
}


CJK = re.compile(r"[\u4e00-\u9fff]")


def tokens(s):
    """中文取 2-gram，英文/数字按词切分。

    中文没有空格，"性能优化" 无法靠 split 匹配到 "渲染性能怎么优化"，
    必须切 2-gram：性能 / 能优 / 优化 → 其中两个出现在问句里即可命中。
    """
    s = s.lower()
    cjk = "".join(CJK.findall(s))
    words = [w for w in re.split(r"[^a-z0-9\u4e00-\u9fff]+", s) if len(w) >= 2]
    grams = [cjk[i:i + 2] for i in range(len(cjk) - 1)]
    return set(grams) | set(words)


def score(name, q_tokens):
    """知识点名与问句的重叠度 0–1。返回连续值，便于排序取 Top N。"""
    t = tokens(name)
    if not t:
        return 0.0
    return len(t & q_tokens) / len(t)


STRONG = 0.4   # 名称强命中阈值


def match_points(udir, question):
    """三级匹配：名称强命中 → 名称弱命中 Top3 → 课程兜底。

    宁可少给也不要乱给：课程兜底只返回与问句确实有重叠的知识点，
    避免问「数据库索引」时把整个数据库课程都端上来。
    """
    qt = tokens(question)
    strong, weak, by_course = [], [], {}
    for path in glob.glob(os.path.join(udir, "points", "*.md")):
        meta, _ = core.read_md(path)
        if meta.get("rejected"):
            continue
        name = str(meta.get("name", ""))
        if not name:
            continue
        t = tokens(name)
        if not t:
            continue
        overlap = len(t & qt)
        s = overlap / len(t)
        if s >= STRONG:
            strong.append((path, meta, s))
        elif overlap >= 2:
            # 弱命中要求**至少重合两个 token**：中文 2-gram 下，
            # 只重合一个词会闹笑话——问「消息传递」把「消息队列」端上来
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
        if not course or score(course, qt) <= 0:
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
            print(f"   · {meta.get('name')}：{label}{tag} "
                  f"current={cur:.0f} 上次接触 {meta.get('last_verified_at')}{via}")
            print(f"     → {ADVICE[status]}")

    pbs = match_playbooks(udir, question)
    print(f"\n② 经验 Playbook：{'命中 ' + str(len(pbs)) + ' 条' if pbs else '无'}")
    for pb in pbs:
        print(f"   · {pb.get('name')}（适用：{pb.get('applicable_when')}）")

    feats = load_features(udir)
    print(f"\n③ 行为画像：{len(feats)} 条已确认特征")
    for f in feats[:3]:
        print(f"   · {f.get('feature')}：{f.get('value')}")

    print("\n④ 建议：回答后写入 questions/ 日志；"
          "若暴露遗忘，记一条负向证据。")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--q", required=True)
    a = p.parse_args()
    query(a.user, a.q)


if __name__ == "__main__":
    main()
