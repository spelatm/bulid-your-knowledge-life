#!/usr/bin/env python3
"""录入证据并重算分数。所有轨的写入统一入口。

用法：
    # 正向：主导项目点亮知识点
    python3 ingest.py --user u001 --target kp_ab12cd34 \
        --type project_lead --conf 0.9 --note "主导支付重构"

    # 负向：本该会却没想起来
    python3 ingest.py --user u001 --target kp_ab12cd34 --type forgot

    # 更新最后验证时间（刷新衰减）
    python3 ingest.py --user u001 --target kp_ab12cd34 --verify
"""
import os
import argparse
import datetime
import core

NEGATIVE = {"forgot", "selftest_fail", "rusty_asked"}


def find_point(udir, target_id):
    path = os.path.join(udir, "points", f"{target_id}.md")
    return path if os.path.exists(path) else None


def ingest(user_id, target_id, ev_type, confidence=None, note="", source_ref=""):
    udir = core.user_dir(user_id)
    path = find_point(udir, target_id)
    if not path:
        return f"未找到知识点 {target_id}"

    meta, body = core.read_md(path)
    weights = core.load_weights()
    if ev_type not in weights:
        return f"未知证据类型 {ev_type}，请检查 _meta/weights.md"

    w, default_conf = weights[ev_type]
    conf = confidence if confidence is not None else default_conf

    # 追加证据（append-only）
    ev_id = core.new_id("ev")
    today = core.TODAY.isoformat()
    core.write_md(
        os.path.join(udir, "evidence", f"{ev_id}.md"),
        {"id": ev_id, "target_type": "point", "target_id": target_id,
         "type": ev_type, "weight": w, "confidence": conf,
         "direction": "negative" if ev_type in NEGATIVE else "positive",
         "coefficient": w if ev_type in NEGATIVE else "",
         "occurred_at": today, "source_ref": source_ref, "note": note},
    )

    # 重算
    raw = float(meta.get("raw_score", 0))
    ev_ids = meta.get("evidence_ids") or []
    if isinstance(ev_ids, str):
        ev_ids = []
    ev_ids.append(ev_id)

    if ev_type in NEGATIVE:
        raw = raw * w                      # 负向：乘系数
    else:
        raw = core.apply_evidence(raw, w, conf, len(ev_ids))

    raw = max(0.0, min(100.0, raw))
    peak = max(float(meta.get("peak_score", 0)), raw)
    current, _ = core.apply_decay(raw, today, meta.get("profile", "foundation"))
    status, base = core.judge_status(raw, current, peak)

    meta.update({"raw_score": round(raw, 1), "current_score": round(current, 1),
                 "peak_score": round(peak, 1), "last_verified_at": today,
                 "evidence_ids": ev_ids, "status": status})
    core.write_md(path, meta, body)

    label = core.LEVEL_LABEL.get(base, base)
    rusty = "（已生疏）" if status == "rusty" else ""
    return (f"{meta.get('name', target_id)}：{label}{rusty} "
            f"raw={raw:.1f} current={current:.1f}")


def verify(user_id, target_id):
    """仅刷新 last_verified_at，让 current 回弹到 raw。"""
    udir = core.user_dir(user_id)
    path = find_point(udir, target_id)
    if not path:
        return f"未找到知识点 {target_id}"
    meta, body = core.read_md(path)
    today = core.TODAY.isoformat()
    raw = float(meta.get("raw_score", 0))
    meta.update({"last_verified_at": today, "current_score": round(raw, 1)})
    _, base = core.judge_status(raw, raw, float(meta.get("peak_score", raw)))
    meta["status"] = base
    core.write_md(path, meta, body)
    return f"{meta.get('name', target_id)} 已刷新，current 回到 {raw:.1f}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--type", default="")
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--note", default="")
    p.add_argument("--source", default="")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    if a.verify:
        print(verify(a.user, a.target))
    elif a.type:
        print(ingest(a.user, a.target, a.type, a.conf, a.note, a.source))
    else:
        p.error("需指定 --type 或 --verify")


if __name__ == "__main__":
    main()
