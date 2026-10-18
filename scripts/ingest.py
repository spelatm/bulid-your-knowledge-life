#!/usr/bin/env python3
"""录入证据并重算分数。所有轨的写入统一入口。

一个知识点：
    python3 ingest.py --user u001 --target 消息传递机制 \
        --type project_lead --note "主导支付重构"

**一条证据点亮多个知识点**（横向边的共现信号就来自这里）：
    python3 ingest.py --user u001 --target 消息传递机制 --target 谱图理论 \
        --type artifact --note "论文复现里两个都用到了"

技能（`--skill`，熟练度独立计算，不与知识点互相推导）：
    python3 ingest.py --user u001 --target 图神经网络工程实现 --skill \
        --type project_lead --note "独立复现了三篇 GNN 论文"

负向 / 刷新：
    python3 ingest.py --user u001 --target 消息传递机制 --type forgot
    python3 ingest.py --user u001 --target 消息传递机制 --verify

注：`--target` 接受 id、知识点名或文件名主干。自 3.4.0 起文件名是知识点名，
不再是 `kp_<哈希>.md`，所以取址统一走 core.find_point，不拼路径。
"""
import os
import argparse
import core

NEGATIVE = {"forgot", "selftest_fail", "rusty_asked"}


def resolve(udir, key, target_type="point"):
    return (core.find_skill(udir, key) if target_type == "skill"
            else core.find_point(udir, key))


def ingest(user_id, targets, ev_type, confidence=None, note="", source_ref="",
           target_type="point"):
    udir = core.user_dir(user_id)
    weights = core.load_weights()
    if ev_type not in weights:
        return f"未知证据类型 {ev_type}，请检查 _meta/weights.md"
    w, default_conf = weights[ev_type]
    conf = confidence if confidence is not None else default_conf

    hits, keys = [], []
    for key in targets:
        hit = resolve(udir, key, target_type)
        if not hit:
            return f"未找到{'技能' if target_type == 'skill' else '知识点'}「{key}」"
        if str(hit[1]["id"]) in keys:
            continue
        keys.append(str(hit[1]["id"]))
        hits.append(hit)

    today = core.TODAY.isoformat()
    ev_id = core.new_id("ev")
    core.write_md(
        os.path.join(udir, "evidence", f"{ev_id}.md"),
        {"id": ev_id, "target_type": target_type, "target_id": keys[0],
         "target_ids": keys,
         "type": ev_type, "weight": w, "confidence": conf, "role": "",
         "direction": "negative" if ev_type in NEGATIVE else "positive",
         "coefficient": w if ev_type in NEGATIVE else "",
         "occurred_at": today, "source_ref": source_ref, "note": note},
    )

    out = []
    for path, meta, body in hits:
        ev_ids = meta.get("evidence_ids") or []
        if isinstance(ev_ids, str):
            ev_ids = [ev_ids] if ev_ids else []
        if ev_id not in ev_ids:
            ev_ids.append(ev_id)
        meta["evidence_ids"] = ev_ids

        if target_type == "skill":
            meta["last_used_at"] = today
            if ev_type in NEGATIVE:
                lvl = float(meta.get("level", 0) or 0) * w
                meta["level"] = round(max(0.0, min(100.0, lvl)), 1)
            else:
                raw, _miss = core.recompute_raw(ev_ids, udir)
                meta["level"] = round(raw, 1)
            core.write_md(path, meta, body)
            out.append(f"{meta.get('name', keys[0])}：熟练度 "
                       f"{float(meta['level']):.1f}")
            continue

        meta["last_verified_at"] = today
        if ev_type in NEGATIVE:
            # 负向乘系数：不走重算，否则会丢掉「曾经到过多少」的语义
            raw = float(meta.get("raw_score", 0) or 0) * w
        else:
            raw, _miss = core.recompute_raw(ev_ids, udir)
        raw = max(0.0, min(100.0, raw))
        peak = max(float(meta.get("peak_score", 0) or 0), raw)
        current, _ = core.apply_decay(raw, today,
                                      meta.get("profile", "foundation"))
        status, base = core.judge_status(raw, current, peak)
        meta.update({"raw_score": round(raw, 1),
                     "current_score": round(current, 1),
                     "peak_score": round(peak, 1), "status": status})
        core.write_md(path, meta, body)
        label = core.LEVEL_LABEL.get(base, base)
        rusty = "（已生疏）" if status == "rusty" else ""
        out.append(f"{meta.get('name', keys[0])}：{label}{rusty} "
                   f"raw={raw:.1f} current={current:.1f}")
    core.invalidate(udir)      # 改的是内容，目录签名不变，缓存必须手动丢
    return "\n".join(out)


def verify(user_id, target, target_type="point"):
    """仅刷新时间戳，让 current 回弹到 raw / 熟练度。"""
    udir = core.user_dir(user_id)
    hit = resolve(udir, target, target_type)
    if not hit:
        return f"未找到「{target}」"
    path, meta, body = hit
    today = core.TODAY.isoformat()
    if target_type == "skill":
        meta["last_used_at"] = today
        core.write_md(path, meta, body)
        core.invalidate(udir)
        return f"{meta.get('name')} 已刷新使用时间"
    raw = float(meta.get("raw_score", 0))
    meta.update({"last_verified_at": today, "current_score": round(raw, 1)})
    _, base = core.judge_status(raw, raw, float(meta.get("peak_score", raw)))
    meta["status"] = base
    core.write_md(path, meta, body)
    core.invalidate(udir)
    return f"{meta.get('name', target)} 已刷新，current 回到 {raw:.1f}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--target", action="append", required=True,
                   help="知识点/技能名或 id，可重复（一条证据点亮多个）")
    p.add_argument("--skill", action="store_true", help="目标是技能实体")
    p.add_argument("--type", default="")
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--note", default="")
    p.add_argument("--source", default="")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    kind = "skill" if a.skill else "point"
    if a.verify:
        print(verify(a.user, a.target[0], kind))
    elif a.type:
        print(ingest(a.user, a.target, a.type, a.conf, a.note, a.source, kind))
    else:
        p.error("需指定 --type 或 --verify")


if __name__ == "__main__":
    main()
