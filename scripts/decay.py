#!/usr/bin/env python3
"""每日衰减：全库重算 current_score 与状态，输出遗忘清单。

用法：
    python3 decay.py --user u001            # 更新并输出生疏清单
    python3 decay.py --user u001 --apply    # 写回档案
"""
import os
import glob
import argparse
import core


def run(user_id, apply_changes=False):
    udir = core.user_dir(user_id)
    files = glob.glob(os.path.join(udir, "points", "*.md"))
    rusty, updated = [], 0

    for path in files:
        meta, body = core.read_md(path)
        if meta.get("rejected"):
            continue
        raw = float(meta.get("raw_score", 0))
        if raw <= 0:
            continue
        current, delta = core.apply_decay(
            raw, meta.get("last_verified_at"), meta.get("profile", "foundation"))
        peak = float(meta.get("peak_score", raw))
        status, base = core.judge_status(raw, current, peak)

        if status == "rusty":
            rusty.append((meta.get("name", os.path.basename(path)),
                          raw, current, peak, delta))

        if apply_changes:
            meta.update({"current_score": round(current, 1), "status": status})
            core.write_md(path, meta, body)
            updated += 1

    rusty.sort(key=lambda x: x[2])          # 当前分最低的排最前
    print(f"共 {len(files)} 个知识点，其中 {len(rusty)} 个已生疏。")
    if rusty:
        print("\n正在流失的知识点（Top 10）：")
        for name, raw, cur, peak, d in rusty[:10]:
            print(f"  · {name}：曾达 {peak:.0f} → 现在 {cur:.0f}"
                  f"（{d} 天未接触）")
    if apply_changes:
        print(f"\n已写回 {updated} 条档案。")
    return rusty


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    run(a.user, a.apply)


if __name__ == "__main__":
    main()
