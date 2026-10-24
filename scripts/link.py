#!/usr/bin/env python3
"""横向边：发现、建议、确认、撤销「知识点 ↔ 知识点」的关联。

纵向边（域 → 学科 → 课程 → 知识点）在 `graph/` 骨架里，是公共的；
横向边是**个人的**——它来自证据共现与用户声明，只能长在档案里。

三档（design §6.1）：

| 档 | 条件 | 动作 |
|---|---|---|
| `auto` | 同域 且 共现 ≥3 次 | 直接建，可撤销 |
| `suggest` | 跨域，或共现 1–2 次 | **先问用户**，同意才建 |
| `manual` | 用户主动说「这两个有关系」 | 直接建 |

存储分三层，各司其职：

- **本体**：两个知识点 frontmatter 的 `related: [名字]`
- **展示**：正文 `<!-- related:start -->` 托管块里的 `[[wikilink]]`
  —— Obsidian 的图谱只认正文链接，frontmatter 的纯文本不进图
- **决策**：`edges.md` 登记簿（谁、何时、凭什么、拒过哪对）

建边本身也留一条 `edge_confirm` 证据（权重 0），可追溯且**不影响分数**。

用法：
    python3 scripts/link.py --user u001 --suggest          # 找候选（auto 直接落盘）
    python3 scripts/link.py --user u001 --accept "A" "B"   # 同意建议
    python3 scripts/link.py --user u001 --reject "A" "B"   # 拒绝，此后不再建议
    python3 scripts/link.py --user u001 --add "A" "B"      # 手工声明
    python3 scripts/link.py --user u001 --remove "A" "B"   # 撤销
    python3 scripts/link.py --user u001 --list
"""
import os
import sys
import argparse
import collections
import core

REGISTRY = "edges.md"
MAX_SUGGEST = 3          # §6.3 防骚扰：单次建议上限
AUTO_MIN_COOCCUR = 3     # §6.1 auto 档阈值

HEADER = """# 关联边登记簿

> 边**本体**在两个知识点的 frontmatter `related` 里；这里是**决策记录**：
> 谁在什么时候、凭什么确认或拒绝了哪一对。`rejected` 的对不再被建议。
> 纵向边（学科骨架）不在本表里，它来自 `graph/`。

| A | B | 状态 | 来源 | 共现 | 依据 | 时间 |
|---|---|---|---:|---|---|
"""


# ---------- 登记簿 ----------

def load_edges(udir):
    """返回 {(A, B): {状态, 来源, 共现, 依据, 时间}}，键无序。"""
    path = os.path.join(udir, REGISTRY)
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 4 or cells[0] in ("A",) or cells[0].startswith("-"):
                continue
            a, b = cells[0], cells[1]
            out[_key(a, b)] = {
                "status": cells[2], "origin": cells[3],
                "n": cells[4] if len(cells) > 4 else "",
                "evs": cells[5] if len(cells) > 5 else "",
                "at": cells[6] if len(cells) > 6 else "",
            }
    return out


def save_edges(udir, edges):
    lines = [HEADER.rstrip("\n")]
    for (a, b), v in sorted(edges.items()):
        lines.append(f"| {a} | {b} | {v['status']} | {v['origin']} | "
                     f"{v.get('n', '')} | {v.get('evs', '')} | "
                     f"{v.get('at', '')} |")
    with open(os.path.join(udir, REGISTRY), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _key(a, b):
    return tuple(sorted((str(a), str(b))))


# ---------- 共现 ----------

def cooccurrences(udir, idx):
    """扫证据：一条证据点亮多个知识点 → 两两配对计数。

    这是这套系统独有的信号——任何简历、任何学科目录都做不到
    「从你自己的行为里发现跨域关系」。
    """
    pairs = collections.defaultdict(lambda: {"n": 0, "evs": []})
    evdir = os.path.join(udir, "evidence")
    for fn in sorted(os.listdir(evdir)) if os.path.isdir(evdir) else []:
        if not fn.endswith(".md"):
            continue
        meta, _ = core.read_md(os.path.join(evdir, fn))
        ids = meta.get("target_ids") or [meta.get("target_id")]
        if isinstance(ids, str):
            ids = [ids]
        names = []
        for i in ids:
            hit = idx["by_id"].get(str(i))
            if hit and str(hit[1].get("name", "")) not in names:
                names.append(str(hit[1]["name"]))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                rec = pairs[_key(a, b)]
                rec["n"] += 1
                rec["evs"].append(str(meta.get("id", fn[:-3])))
    return pairs


def same_domain(idx, a, b):
    ma = idx["by_name"].get(a, (None, {}, None))[1]
    mb = idx["by_name"].get(b, (None, {}, None))[1]
    da = str(ma.get("domain", "") or "")
    return bool(da) and da == str(mb.get("domain", "") or "")


# ---------- 写边 ----------

def _render_side(udir, meta, registry, idx):
    """按 related + 登记簿，重建该点正文的托管块。"""
    entries = []
    for name in meta.get("related") or []:
        hit = idx["by_name"].get(str(name))
        if not hit:
            continue          # 名字对不上（改名/删除）→ 不展示，但不静默删字段
        stem = os.path.splitext(os.path.basename(hit[0]))[0]
        rec = registry.get(_key(meta.get("name"), name), {})
        if rec.get("n"):
            note = f"共现 {rec['n']} 次"
        elif rec.get("origin") == "user":
            note = "手工关联"
        else:
            note = ""
        entries.append((str(name), stem, note))
    entries.sort(key=lambda e: e[0])
    return entries


def add_edge(udir, name_a, name_b, origin="user", ev_ids=None, quiet=False):
    """双向写 frontmatter + 正文块 + 登记簿 + 证据。返回一句话结果。"""
    idx = core.index_points(udir)
    a = core.find_point(udir, name_a, idx)
    b = core.find_point(udir, name_b, idx)
    if not a or not b:
        miss = name_a if not a else name_b
        return f"未找到知识点「{miss}」"
    na, nb = str(a[1]["name"]), str(b[1]["name"])
    if na == nb:
        return "是同一个知识点，跳过"

    registry = load_edges(udir)
    n = 1
    if ev_ids:
        n = len(ev_ids)
    registry[_key(na, nb)] = {
        "status": "active", "origin": origin, "n": str(n),
        "evs": ", ".join(ev_ids or [])[:120],
        "at": core.TODAY.isoformat(),
    }
    save_edges(udir, registry)

    # 留痕：权重 0，不改变任何分数（确认关联 ≠ 掌握证据）
    weights = core.load_weights()
    w, conf = weights.get("edge_confirm", (0.0, 1.0))
    ev_id = core.new_id("ev")
    core.write_md(
        os.path.join(udir, "evidence", f"{ev_id}.md"),
        {"id": ev_id, "target_type": "point", "target_id": str(a[1]["id"]),
         "target_ids": [str(a[1]["id"]), str(b[1]["id"])],
         "type": "edge_confirm", "weight": w, "confidence": conf,
         "role": "", "direction": "neutral", "coefficient": "",
         "occurred_at": core.TODAY.isoformat(), "source_ref": f"link:{origin}",
         "note": f"与「{nb}」建立关联（来源 {origin}）"},
    )

    for hit, other in ((a, nb), (b, na)):
        path, meta, body = hit
        rel = [str(x) for x in (meta.get("related") or [])]
        if other not in rel:
            rel.append(other)
        meta["related"] = sorted(rel)
        entries = _render_side(udir, meta, registry, idx)
        core.write_md(path, meta, core.set_related(body, entries))
    if not quiet:
        return f"已建立关联：{na} ↔ {nb}（来源 {origin}，共现 {n} 次）"
    return ""


def remove_edge(udir, name_a, name_b, reason="user"):
    idx = core.index_points(udir)
    a, b = core.find_point(udir, name_a, idx), core.find_point(udir, name_b, idx)
    if not a or not b:
        return "未找到知识点"
    na, nb = str(a[1]["name"]), str(b[1]["name"])
    registry = load_edges(udir)
    registry[_key(na, nb)] = {"status": reason, "origin": "user", "n": "",
                              "evs": "", "at": core.TODAY.isoformat()}
    save_edges(udir, registry)
    for hit, other in ((a, nb), (b, na)):
        rel = [str(x) for x in (hit[1].get("related") or []) if str(x) != other]
        hit[1]["related"] = rel
        entries = _render_side(udir, hit[1], registry, idx)
        core.write_md(hit[0], hit[1], core.set_related(hit[2], entries))
    return f"已撤销关联：{na} ↔ {nb}（{reason}）"


# ---------- 建议 ----------

def suggest(udir, auto_create=True):
    """扫共现 → auto 档直接建，其余按「跨域优先 + 次数」排序取前 3 条建议。"""
    idx = core.index_points(udir)
    pairs = cooccurrences(udir, idx)
    registry = load_edges(udir)
    related = {_key(m.get("name"), x)
               for _p, m, _b in idx["items"] for x in (m.get("related") or [])}

    created, cand = [], []
    for key, rec in pairs.items():
        if key in related:
            continue
        if registry.get(key, {}).get("status") == "rejected":
            continue          # 拒过的同一对不再建议（§6.3）
        a, b = key
        if a not in idx["by_name"] or b not in idx["by_name"]:
            continue
        cross = not same_domain(idx, a, b)
        if not cross and rec["n"] >= AUTO_MIN_COOCCUR and auto_create:
            add_edge(udir, a, b, origin="cooccur", ev_ids=rec["evs"], quiet=True)
            created.append((a, b, rec["n"]))
        else:
            cand.append({"a": a, "b": b, "n": rec["n"], "evs": rec["evs"],
                         "cross": cross})

    # 跨域优先：跨域边噪声最大、价值也最大，必须让用户拍板
    cand.sort(key=lambda x: (not x["cross"], -x["n"], x["a"]))
    return created, cand[:MAX_SUGGEST], len(cand)


def format_suggest(created, cand, total):
    out = []
    if created:
        out.append(f"自动建边 {len(created)} 条（同域且共现 ≥{AUTO_MIN_COOCCUR} 次，可撤销）：")
        for a, b, n in created:
            out.append(f"  · {a} ↔ {b}（共现 {n} 次）")
        out.append("")
    if not cand:
        out.append("没有待确认的关联候选。")
        return "\n".join(out)
    out.append(f"发现 {total} 组共现，取前 {len(cand)} 条请你确认"
               f"（同一对拒绝后不再问）：")
    out.append("")
    for c in cand:
        why = "跨域" if c["cross"] else "同域"
        out.append(f"「{c['a']}」和「{c['b']}」同时出现在 "
                   f"{c['n']} 条证据里（{why}）——这条线要连上吗？")
        out.append(f"  依据：{', '.join(c['evs'][:4])}")
    out.append("")
    out.append("确认：--accept \"A\" \"B\"　不连：--reject \"A\" \"B\"")
    return "\n".join(out)


def list_edges(udir):
    idx = core.index_points(udir)
    rows = []
    for _p, m, _b in idx["items"]:
        for x in (m.get("related") or []):
            key = _key(m.get("name"), x)
            if key not in rows:
                rows.append(key)
    registry = load_edges(udir)
    if not rows:
        return "档案里还没有横向边。跑 --suggest 看看有没有共现。"
    out = [f"共 {len(rows)} 条横向边："]

    def cross(k):
        return not same_domain(idx, k[0], k[1])

    for a, b in sorted(rows, key=lambda k: (not cross(k), k)):
        rec = registry.get((a, b), {})
        tag = "跨域" if cross((a, b)) else "同域"
        out.append(f"  · {a} ↔ {b}　[{tag}/{rec.get('origin', '?')}"
                   f"{'，共现 ' + rec['n'] + ' 次' if rec.get('n') else ''}]")
    return "\n".join(out)


# ---------- 前置边（prerequisite） ----------
#
# 与横向边不同：前置是**有方向的、必须无环的**，用途不是联想而是
# 「讲解顺序」与「可疑标记」。所以它不走 edges.md 登记簿（那是共现决策的记录），
# 也不用正文 wikilink（那不是联想），只写 frontmatter `prerequisite: [名字]`。

def _by_name(udir):
    return core.index_points(udir)["by_name"]


def prereq_of(udir, name, index=None):
    """返回某个知识点的前置名字列表（不存在的条目返回空）。"""
    hit = (index or _by_name(udir)).get(str(name))
    if not hit:
        return []
    return [str(x) for x in (hit[1].get("prerequisite") or [])]


def _all_prereqs(udir):
    """全库前置图：{名字: [前置名字]}。"""
    out = {}
    for name, (_p, m, _b) in _by_name(udir).items():
        pre = [str(x) for x in (m.get("prerequisite") or [])]
        if pre:
            out[name] = pre
    return out


def _reachable(graph, start, goal, seen=None):
    """从 start 顺着前置往上走，能否到达 goal。"""
    seen = seen or set()
    if start == goal:
        return True
    if start in seen:
        return False
    seen.add(start)
    return any(_reachable(graph, nxt, goal, seen)
               for nxt in graph.get(start, []))


def set_prereq(udir, target, need, add=True):
    """`target` 需要 `need` 作为前置。加边前检查环；成环直接拒绝。"""
    idx = _by_name(udir)
    if str(target) not in idx:
        return f"未找到知识点：{target}"
    if str(need) not in idx:
        return f"未找到知识点：{need}"
    graph = _all_prereqs(udir)
    if add and _reachable(graph, str(need), str(target)):
        return (f"拒绝：{need} 已经（直接或间接）依赖 {target}，"
                f"再加这条会成环——前置必须是 DAG")
    path, meta, body = idx[str(target)]
    cur = [str(x) for x in (meta.get("prerequisite") or [])]
    if add:
        if str(need) in cur:
            return f"{target} 的前置里已经有 {need}"
        cur.append(str(need))
    else:
        if str(need) not in cur:
            return f"{target} 的前置里没有 {need}"
        cur.remove(str(need))
    meta["prerequisite"] = cur
    core.write_md(path, meta, body)
    core.invalidate(udir)
    verb = "加上" if add else "去掉"
    return f"已{verb}前置：{target} ← {need}"


def _only_inferred(udir, meta):
    """这条知识点的分是不是**只来自冷启动推断**（没有一条实测证据）。

    为什么要分这一层：推断分的置信度天然低，拿它判「你懂下游却不懂上游」
    会天天报警。真正值得警觉的是**有实测证据**却缺前置。
    """
    ids = meta.get("evidence_ids") or []
    if isinstance(ids, str):
        ids = [ids] if ids else []
    if not ids:
        return False                # 没证据却有分才是异常，交给别的检查
    for eid in ids:
        path = os.path.join(udir, "evidence", f"{eid}.md")
        try:
            em, _ = core.read_md(path)
        except OSError:
            return False
        if str(em.get("type", "")) not in ("inferred", "web_inferred"):
            return False            # 有一条实测证据，就算「真的声称会」
    return True


def audit_prereq(udir):
    """返回 (实测可疑, 推断待验证, 断链, 环)。

    可疑 = 这条有分（raw>0）但它的前置还是 0 分——学会了下游却没碰上游，
    要么标错了，要么上游是「自以为会」。这是比「待验证」更有指向的信号。

    再按**分的来源**拆两档：有实测证据的进「实测可疑」，纯冷启动推断的
    进「推断待验证」。两者都该看，但处置不同——前者问用户，后者补一次推断即可。
    """
    idx = _by_name(udir)
    suspicious, inferred, broken, cycles = [], [], [], []
    graph = _all_prereqs(udir)
    for name, pre in graph.items():
        hit = idx.get(name)
        if not hit:
            continue
        meta = hit[1]
        raw = float(meta.get("raw_score", 0) or 0)
        if raw <= 0:
            continue
        only_inf = _only_inferred(udir, meta)
        for p in pre:
            ph = idx.get(p)
            if not ph:
                broken.append((name, p))
                continue
            if float(ph[1].get("raw_score", 0) or 0) > 0:
                continue
            (inferred if only_inf else suspicious).append((name, p, raw))
    # 成环判定不能拿「自己是否可达自己」做起点——那必然为真。
    # 正确的问法是：它的某个前置，顺着前置往上走能不能回到它。
    for name, pre in graph.items():
        if any(_reachable(graph, p, name) for p in pre):
            cycles.append(name)
    return suspicious, inferred, broken, sorted(set(cycles))


def format_prereq(udir, name):
    """给 query 用：这一条的前置分别是什么状态。"""
    idx = _by_name(udir)
    pre = prereq_of(udir, name, idx)
    if not pre:
        return []
    out = [f"前置（{len(pre)} 条）："]
    for p in pre:
        hit = idx.get(p)
        if not hit:
            out.append(f"   · {p}　（档案里没有这条）")
        else:
            raw = float(hit[1].get("raw_score", 0) or 0)
            out.append(f"   · {p}　{'已触及' if raw > 0 else '**未触及**'}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--suggest", action="store_true")
    p.add_argument("--accept", nargs=2, metavar=("A", "B"))
    p.add_argument("--reject", nargs=2, metavar=("A", "B"))
    p.add_argument("--add", nargs=2, metavar=("A", "B"))
    p.add_argument("--remove", nargs=2, metavar=("A", "B"))
    p.add_argument("--list", action="store_true")
    p.add_argument("--prereq", nargs=2, metavar=("A", "B"),
                   help="A 需要 B 作为前置")
    p.add_argument("--unprereq", nargs=2, metavar=("A", "B"))
    p.add_argument("--prereq-audit", action="store_true")
    a = p.parse_args()
    udir = core.user_dir(a.user)
    if not os.path.isdir(udir):
        print(f"用户 {a.user} 不存在")
        return 1
    if a.suggest:
        print(format_suggest(*suggest(udir)))
    elif a.accept:
        # 建议是「基于共现」提出的，确认时把那份依据一并落到登记簿里
        idx = core.index_points(udir)
        rec = cooccurrences(udir, idx).get(_key(a.accept[0], a.accept[1]),
                                          {"evs": []})
        print(add_edge(udir, a.accept[0], a.accept[1], origin="confirmed",
                       ev_ids=rec["evs"]))
    elif a.add:
        print(add_edge(udir, a.add[0], a.add[1], origin="user"))
    elif a.reject:
        print(remove_edge(udir, a.reject[0], a.reject[1], reason="rejected"))
    elif a.remove:
        print(remove_edge(udir, a.remove[0], a.remove[1], reason="removed"))
    elif a.list:
        print(list_edges(udir))
    elif a.prereq:
        print(set_prereq(udir, a.prereq[0], a.prereq[1], add=True))
    elif a.unprereq:
        print(set_prereq(udir, a.unprereq[0], a.unprereq[1], add=False))
    elif a.prereq_audit:
        sus, inf, broken, cyc = audit_prereq(udir)
        print(f"前置可疑 {len(sus)} 条（有实测证据）｜推断待验证 {len(inf)} 条"
              f"｜断链 {len(broken)} 条｜成环 {len(cyc)} 条")
        for n, p, r in sus[:20]:
            print(f"  · {n}（{r:.0f} 分）的前置 {p} 还是 0 分")
        for n, p, r in inf[:10]:
            print(f"  · （推断分）{n}（{r:.0f} 分）的前置 {p} 还没碰过")
        for n, p in broken[:10]:
            print(f"  · 断链：{n} ← {p}（档案里没有这条）")
        for n in cyc[:10]:
            print(f"  · 成环：{n}")
    else:
        p.error("需要一个动作：--suggest / --accept / --reject / --add / --remove / "
            "--list / --prereq / --unprereq / --prereq-audit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
