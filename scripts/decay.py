#!/usr/bin/env python3
"""每日衰减：全库重算 current_score 与状态，输出遗忘清单。

用法：
    python3 decay.py --user u001            # 更新并输出生疏清单
    python3 decay.py --user u001 --apply    # 写回档案
"""
import os
import argparse
import core


def run(user_id, apply_changes=False):
    udir = core.user_dir(user_id)
    # 走索引（带落盘缓存）：500 条逐个 open 要十几秒，而这个脚本每次问答后都可能跑
    items = core.index_points(udir)["items"]
    rusty, updated = [], 0

    for path, meta, body in items:
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
            new_cur = round(current, 1)
            if (abs(float(meta.get("current_score", -1) or -1) - new_cur) > 0.05
                    or str(meta.get("status")) != status):
                meta.update({"current_score": new_cur, "status": status})
                core.write_md(path, meta, body)
                updated += 1

    if apply_changes:
        core.invalidate(udir)      # 改了内容，目录签名不变，缓存要手动丢

    rusty.sort(key=lambda x: x[2])          # 当前分最低的排最前
    print(f"共 {len(items)} 个知识点，其中 {len(rusty)} 个已生疏。")
    if rusty:
        print("\n正在流失的知识点（Top 10）：")
        for name, raw, cur, peak, d in rusty[:10]:
            print(f"  · {name}：曾达 {peak:.0f} → 现在 {cur:.0f}"
                  f"（{d} 天未接触）")
    if apply_changes:
        print(f"\n已写回 {updated} 条档案（分数没变的跳过，不产生无意义写入）。")
    return rusty


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    run(a.user, a.apply)


if __name__ == "__main__":
    main()
