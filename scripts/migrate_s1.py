#!/usr/bin/env python3
"""S1 档案迁移：可读命名 + 字段统一 + 清理发明字段。

**幂等、可重复运行，且不碰任何分数与证据。**

它做四件事（design/参照系与耦合层方案.md §11.6）：

  ① 命名可读化   kp_<hash>.md → <知识点名>.md
                  非法字符转全角、跨学科重名加（学科）后缀
  ② 补字段       domain / transferable / context / prior_exposure / status
  ③ 删发明字段   connections / application / related_to（v0.2 误加，见方案 §4.1）
  ④ 重名消歧     只改文件名，**不合并数据**

自检红线：迁移前后 raw_score 合计、证据条数必须完全一致。

用法：
    python3 migrate_s1.py --user default --dry-run     # 只看对照，不写入
    python3 migrate_s1.py --user default               # 正式执行
    python3 migrate_s1.py --all                        # users/ 下全部用户
"""
import os
import glob
import argparse
import collections
import core

# v0.2 误加的三个字段（方案 §4.1 已更正来源），本脚本负责清除
INVENTED = ("connections", "application", "related_to")

# 落盘字段顺序：让「域 / 切面 / 先验」紧挨 subject/course，Obsidian 面板更好读
FIELDS_ORDER = ["id", "name", "subject", "course", "domain",
                "transferable", "context", "profile", "importance",
                "prior_exposure", "raw_score", "current_score", "peak_score",
                "status", "last_verified_at", "origin", "rejected",
                "evidence_ids", "tags"]


def raw_of(meta):
    try:
        return float(meta.get("raw_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def order_meta(meta):
    """按 FIELDS_ORDER 排序，未列出的字段按原顺序追加在末尾。"""
    out = {k: meta[k] for k in FIELDS_ORDER if k in meta}
    for k, v in meta.items():
        if k not in out:
            out[k] = v
    return out


def collect(udir):
    """读取全部知识点，返回 [(path, meta, body)]，按 (name, id) 确定性排序。"""
    items = []
    for path in glob.glob(os.path.join(udir, "points", "*.md")):
        meta, body = core.read_md(path)
        items.append((path, meta, body))
    items.sort(key=lambda it: (str(it[1].get("name", "")),
                               str(it[1].get("id", ""))))
    return items


def plan_names(items):
    """算出每条的目标文件名。返回 [(path, new_filename)]。

    重名判定**只依据 meta 里的 name**（不看当前文件名），因此幂等：
    第二次运行会算出与第一次完全相同的结果。
    """
    base = {path: core.safe_name(meta.get("name")) for path, meta, _ in items}
    dup = collections.Counter(base.values())
    used, plan = set(), []
    for path, meta, _ in items:
        stem = base[path]
        if dup[stem] > 1:                       # 跨学科重名 → 加学科后缀消歧
            stem = core.safe_name(meta.get("name"), meta.get("subject"))
        k, n = stem, 1
        while k in used:                        # 同名同学科 → 追加序号
            n += 1
            k = f"{stem}-{n}"
        used.add(k)
        plan.append((path, k + ".md"))
    return plan


def migrate(user_id, dry_run=False):
    udir = core.user_dir(user_id)
    if not os.path.isdir(udir):
        print(f"用户 {user_id} 不存在，跳过。")
        return False
    items = collect(udir)
    if not items:
        print(f"用户 {user_id} 没有知识点，跳过。")
        return False
    cfg = core.load_zone_config()

    # ---- 先验需要的上下文：哪些学科 / 域已被触及 ----
    touched_subj = {str(m.get("subject", "")) for _, m, _ in items
                    if raw_of(m) > 0}
    touched_dom = {core.domain_of(m.get("subject"), m.get("course"), cfg)
                   for _, m, _ in items if raw_of(m) > 0}
    touched_dom.discard("")

    # ---- 目标文件名 ----
    nameplan = dict(plan_names(items))

    # ---- 逐条生成新 meta ----
    out, renamed, illegal, invented_hits, status_added = [], 0, 0, 0, 0
    for path, meta, body in items:
        m = dict(meta)
        subj, course = str(m.get("subject", "")), str(m.get("course", ""))
        probe = {"subject": subj, "course": course,
                 "name": m.get("name", ""), "raw_score": m.get("raw_score", 0)}

        m["domain"] = core.domain_of(subj, course, cfg)
        m["transferable"] = core.facet_of(probe, "transferable", cfg)
        m["context"] = core.facet_of(probe, "context", cfg)
        m["prior_exposure"] = core.prior_of(
            probe, {"subject_touched": subj in touched_subj,
                    "domain_touched": m["domain"] in touched_dom}, cfg)

        raw = raw_of(m)
        cur = float(m.get("current_score", 0) or 0)
        peak = float(m.get("peak_score", 0) or 0)
        new_status = core.judge_status(raw, cur, peak)[0]
        if m.get("status") != new_status:
            status_added += 1
        m["status"] = new_status

        for k in INVENTED:
            if k in m:
                invented_hits += 1
                m.pop(k)
        m = order_meta(m)

        newname = nameplan[path]
        if os.path.basename(path) != newname:
            renamed += 1
        if core.safe_name(meta.get("name")) != str(meta.get("name")):
            illegal += 1
        out.append((path, newname, m, body))

    # ---- 自检：分数不许变 ----
    before = sum(raw_of(m) for _, m, _ in items)
    after = sum(raw_of(m) for _, _, m, _ in out)
    assert abs(before - after) < 1e-6, f"分数被改动了！{before} → {after}"

    # ---- 报告 ----
    domains = collections.Counter(m.get("domain") or "未归类"
                                  for _, _, m, _ in out)
    priors = collections.Counter(str(m.get("prior_exposure")) for _, _, m, _ in out)
    print(f"=== S1 迁移{'预演' if dry_run else ''} · 用户 {user_id} ===")
    print(f"知识点总数：{len(out)}")
    print(f"① 命名可读化：重命名 {renamed} 条"
          f"（含非法字符 {illegal} 条）")
    print(f"② 字段补齐：domain / transferable / context / prior_exposure 各 {len(out)} 条，"
          f"status 新补 {status_added}")
    print(f"③ 清理发明字段：命中 {invented_hits} 处（{len(INVENTED)} 个字段名）")
    print(f"④ 分数自检：raw 合计 {before:.1f} → {after:.1f} ✓")
    print(f"\n域分布：")
    for k, v in domains.most_common():
        print(f"    {k:<18}{v}")
    print(f"\n先验分布：{dict(priors)}")

    dups = [n for n, c in collections.Counter(
        core.safe_name(m.get("name")) for _, _, m, _ in out).items() if c > 1]
    if dups:
        print(f"\n跨学科重名（已加学科后缀消歧）：{'、'.join(dups)}")

    renamed_list = [(os.path.basename(p), n) for p, n, _, _ in out
                    if os.path.basename(p) != n]
    if renamed_list:
        print(f"\n重命名示例（前 8 条）：")
        for old, new in renamed_list[:8]:
            print(f"    {old}  →  {new}")

    if dry_run:
        print("\n（预演模式，未写入任何文件）")
        return True

    # ---- 落盘：先写新，再删旧。目标名批内唯一，不会互相覆盖 ----
    pdir = os.path.join(udir, "points")
    for old, newname, m, body in out:
        new = os.path.join(pdir, newname)
        core.write_md(new, m, body)
        if os.path.abspath(new) != os.path.abspath(old):
            os.remove(old)
    print(f"\n已写入 {len(out)} 条。")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--all", action="store_true", help="users/ 下全部用户")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    users = []
    if a.all:
        for p in sorted(glob.glob(os.path.join(core.ROOT, "users", "*"))):
            if os.path.isdir(p) and os.path.basename(p) != "__pycache__":
                users.append(os.path.basename(p))
    elif a.user:
        users = [a.user]
    else:
        ap.error("请给 --user <id> 或 --all")

    for u in users:
        migrate(u, a.dry_run)
        print()


if __name__ == "__main__":
    main()
