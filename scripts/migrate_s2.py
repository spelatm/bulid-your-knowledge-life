#!/usr/bin/env python3
"""S2 迁移：证据可以点亮多个点 + 种子证据显式化 + 重名合并。

四步，**全部幂等、支持 --dry-run、除重名合并外分数零变化**：

  ① 证据补 `target_ids`：单目标 → 列表（`target_id` 保留，老脚本不会炸）
  ② 种子证据补 `role: seed`：旧记录按「推断类 + 权重 ≥20」识别
     （种子是**直接赋值**，不是边际累加——不标出来，两条种子会被加在一起）
  ③ `raw>0` 却没有证据的条目 → **补录**一条等值种子证据
     （3.4.0 的静态推断直接写分没留证据，违反 I2；补录后分数不变、可审计）
  ④ 同一知识点名出现在多个学科下 → 合并成一条，分数按证据重算

为什么必须做 ①②：横向边靠「一条证据同时点亮多个知识点」的**共现**来发现，
`target_id` 是单值就永远共现不了；而种子证据若不显式，重算时会被当成
普通证据叠加，凭空涨分。

用法：
    python3 scripts/migrate_s2.py --user default --dry-run
    python3 scripts/migrate_s2.py --user default
"""
import os
import sys
import argparse
import collections
import core


def norm_evidence(udir, dry):
    """① 补 target_ids　② 补 role: seed"""
    changed = {"target_ids": 0, "seed": 0}
    for path in sorted(os.listdir(os.path.join(udir, "evidence"))):
        if not path.endswith(".md"):
            continue
        p = os.path.join(udir, "evidence", path)
        meta, body = core.read_md(p)
        if not meta.get("id"):
            continue
        touched = False
        if not meta.get("target_ids"):
            tid = str(meta.get("target_id", "") or "")
            meta["target_ids"] = [tid] if tid else []
            changed["target_ids"] += 1
            touched = True
        if core.is_seed(meta) and str(meta.get("role", "")) != "seed":
            meta["role"] = "seed"
            changed["seed"] += 1
            touched = True
        if touched and not dry:
            core.write_md(p, meta, body)
    return changed


def backfill(udir, items, dry):
    """③ 有分无证据 → 补一条等值种子证据（raw 不变）。"""
    done = []
    for path, meta, body in items:
        raw = float(meta.get("raw_score", 0) or 0)
        ev_ids = meta.get("evidence_ids") or []
        if isinstance(ev_ids, str):
            ev_ids = [ev_ids] if ev_ids else []
        if raw <= 0 or ev_ids:
            continue
        ev_id = core.new_id("ev") if not dry else f"ev_DRYRUN_{meta['id']}"
        if not dry:
            core.write_md(
                os.path.join(udir, "evidence", f"{ev_id}.md"),
                {"id": ev_id, "target_type": "point",
                 "target_id": meta["id"], "target_ids": [meta["id"]],
                 # 权重 = 原分值、置信度 1.0、role=seed → 重算必然回到原分
                 "type": "inferred", "weight": raw, "confidence": 1.0,
                 "role": "seed", "direction": "positive", "coefficient": "",
                 "occurred_at": str(meta.get("last_verified_at")
                                    or core.TODAY.isoformat()),
                 "source_ref": "backfill",
                 "note": "补录：冷启动种子分（3.4.0 写入时未留证据）"},
            )
            meta["evidence_ids"] = [ev_id]
            core.write_md(path, meta, body)
        done.append((str(meta.get("name")), str(meta.get("subject")), raw))
    return done


def _ev_list(meta):
    ev = meta.get("evidence_ids") or []
    if isinstance(ev, str):
        ev = [ev] if ev else []
    return [str(x) for x in ev]


def merge_dups(udir, items, dry):
    """④ 同名跨学科 → 合并。保留者优先有 domain 的（它已被正确归类）。"""
    g = collections.defaultdict(list)
    for it in items:
        g[str(it[1].get("name", ""))].append(it)
    merged = []
    for name, group in g.items():
        if len(group) < 2 or not name:
            continue
        keep = max(group, key=lambda it: (
            bool(str(it[1].get("domain", "") or "").strip()),
            float(it[1].get("raw_score", 0) or 0),
            len(_ev_list(it[1])),
        ))
        keep_path, keep_meta, keep_body = keep
        ev = []
        for _, m, _b in group:
            for e in _ev_list(m):
                if e not in ev:
                    ev.append(e)
        raw, missing = core.recompute_raw(ev, udir)
        peak = max([float(m.get("peak_score", 0) or 0) for _, m, _b in group]
                   + [raw])
        profile = str(keep_meta.get("profile", "foundation"))
        last = max([str(m.get("last_verified_at") or "") for _, m, _b in group])
        current, _ = core.apply_decay(raw, last or None, profile)
        status, _base = core.judge_status(raw, current, peak)
        tags = []
        for _, m, _b in group:
            t = m.get("tags") or []
            if isinstance(t, str):
                t = [t]
            tags += [x for x in t if x not in tags]

        losers = [(p, m) for p, m, _b in group if p != keep_path]
        merged.append({
            "name": name, "keep": keep_path, "drop": [p for p, _ in losers],
            "raw_before": [float(m.get("raw_score", 0) or 0)
                           for _p, m, _b in group],
            "raw_after": raw, "missing": missing,
        })
        if dry:
            continue
        keep_meta.update({
            "raw_score": round(raw, 1), "current_score": round(current, 1),
            "peak_score": round(peak, 1), "status": status,
            "last_verified_at": last, "evidence_ids": ev, "tags": tags,
        })
        for p, _m in losers:
            os.remove(p)
        # 撞名消失后，文件名回到纯知识点名（Obsidian 里才连得上）
        plain = os.path.join(os.path.dirname(keep_path),
                             core.safe_name(name) + ".md")
        if keep_path != plain and not os.path.exists(plain):
            os.rename(keep_path, plain)
            merged[-1]["keep"] = plain
        core.write_md(merged[-1]["keep"], keep_meta, keep_body)
    return merged


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    udir = core.user_dir(a.user)
    if not os.path.isdir(udir):
        print(f"用户 {a.user} 不存在")
        return 1
    dry = a.dry_run
    tag = "（试运行，未落盘）" if dry else ""

    idx = core.index_points(udir)
    items = idx["items"]
    before = {str(m["id"]): float(m.get("raw_score", 0) or 0) for _p, m, _b in items}
    total_before = sum(before.values())

    print(f"S2 迁移 · 用户 {a.user}　知识点 {len(items)} 条"
          f"　raw 合计 {total_before:.1f} {tag}\n")

    ch = norm_evidence(udir, dry)
    print(f"① 证据补 target_ids：{ch['target_ids']} 条"
          f"　② 种子证据补 role：{ch['seed']} 条")

    bf = backfill(udir, items, dry)
    print(f"③ 有分无证据 → 补录种子证据：{len(bf)} 条"
          + ("（分数不变）" if bf else ""))
    for name, subject, raw in bf[:5]:
        print(f"     · {name}（{subject}）raw={raw:.0f}")
    if len(bf) > 5:
        print(f"     … 其余 {len(bf) - 5} 条")

    merged = merge_dups(udir, items, dry)
    print(f"④ 同名跨学科合并：{len(merged)} 组")
    for m in merged:
        print(f"     · {m['name']}：{m['raw_before']} → {m['raw_after']:.1f}"
              f"　保留 {os.path.basename(m['keep'])}"
              f"　删除 {[os.path.basename(x) for x in m['drop']]}")
        if m["missing"]:
            print(f"       ⚠ 证据缺失：{m['missing']}")

    # 对账：除合并组外，任何条目 raw 变动都是 bug
    if not dry:
        after_idx = core.index_points(udir)
        merged_ids = {m["name"] for m in merged}
        drift = []
        for _p, m, _b in after_idx["items"]:
            if str(m.get("name")) in merged_ids:
                continue
            old = before.get(str(m["id"]))
            if old is not None and abs(old - float(m.get("raw_score", 0) or 0)) > 0.05:
                drift.append((m.get("name"), old, m.get("raw_score")))
        total_after = sum(float(m.get("raw_score", 0) or 0)
                          for _p, m, _b in after_idx["items"])
        print(f"\nraw 合计：{total_before:.1f} → {total_after:.1f}"
              f"（差 {total_after - total_before:+.1f}，应全部来自合并）")
        print(f"条目数：{len(items)} → {len(after_idx['items'])}")
        if drift:
            print(f"⚠ 有 {len(drift)} 条未合并条目分数漂移：{drift[:5]}")
            return 2
        # 可复算性：每条有证据的条目，raw 必须能由证据重算得出
        bad = []
        for _p, m, _b in after_idx["items"]:
            ev = _ev_list(m)
            if not ev:
                continue
            raw, missing = core.recompute_raw(ev, udir)
            if missing or abs(raw - float(m.get("raw_score", 0) or 0)) > 0.2:
                bad.append((m.get("name"), m.get("raw_score"), round(raw, 1)))
        if bad:
            print(f"⚠ {len(bad)} 条分数无法由证据复算（前 5）：{bad[:5]}")
            return 3
        print("✓ 全部有证据的条目均可由证据重算得出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
