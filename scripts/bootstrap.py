#!/usr/bin/env python3
"""启动引导：检查用户档案状态，输出 agent 下一步该做什么。

这是整个 Skill 的**入口**。agent 加载本 Skill 后第一件事就是跑它，
按输出的「下一步」执行，不要自己判断。

用法：
    python3 bootstrap.py --check --user u001
    python3 bootstrap.py --check --user u001 --json
"""
import os
import re
import glob
import json
import argparse
import datetime
import core

ONBOARD_NEW = "new"
ONBOARD_PARTIAL = "partial"
ONBOARD_READY = "ready"

# 冷启动采集的三项。缺任一项即 partial。
FIELDS = [
    ("education", "学历/专业", "比如：计算机本科、高中、机械硕士、自学"),
    ("occupation", "职业/年限", "比如：前端工程师 5 年、教师、学生、自由职业"),
    ("region", "生活/工作区域", "比如：杭州、北京、上海、海外"),
]


def profile_path(user_id):
    return os.path.join(core.user_dir(user_id), "profile.md")


def detect_state(user_id):
    """返回 (状态, meta, 缺失字段列表)"""
    p = profile_path(user_id)
    if not os.path.exists(p):
        return ONBOARD_NEW, {}, [k for k, _, _ in FIELDS]
    meta, _ = core.read_md(p)
    missing = []
    for key, _, _ in FIELDS:
        v = str(meta.get(key, "")).strip()
        if not v or v in ("-", "—", "未知", "未填"):
            missing.append(key)
    if meta.get("onboarding") == "ready" and not missing:
        return ONBOARD_READY, meta, []
    return ONBOARD_PARTIAL, meta, missing


def count_points(user_id):
    """返回 (知识点总数, 已触及数, 最近一次接触日期)。

    走索引而不是 glob+read_md：500 条文件逐个 open 要十几秒，
    而索引有落盘缓存，热起来 0.1 秒。日期取「档案真正动过」的那天，
    不是 profile.md 的 updated_at——后者在录入证据时并不会变。
    """
    udir = core.user_dir(user_id)
    if not os.path.isdir(os.path.join(udir, "points")):
        return 0, 0, ""
    n = touched = 0
    latest = ""
    for _p, m, _b in core.index_points(udir)["items"]:
        n += 1
        if float(m.get("raw_score", 0) or 0) > 0:
            touched += 1
        seen = str(m.get("last_verified_at") or "").strip()
        if seen > latest:
            latest = seen
    return n, touched, latest


def ask_script(missing):
    """生成给用户的询问话术。一次问清，不要逐个追问。"""
    lines = []
    lines.append("我想先把你的知识档案建起来，这样以后回答时能按你的实际水平来讲，")
    lines.append("也能告诉你哪些知识正在生疏。需要三件事，一两句话说完就行：")
    lines.append("")
    for i, (key, label, hint) in enumerate(FIELDS, 1):
        mark = "← 还缺这个" if key in missing else ""
        lines.append(f"{i}. **{label}**：{hint}　{mark}")
    lines.append("")
    lines.append("（不想说也没关系，说一句「先跳过」，我按空白档案开始，"
                 "后面聊到再补。）")
    return "\n".join(lines)


def check(user_id, as_json=False):
    state, meta, missing = detect_state(user_id)
    n, touched, latest = count_points(user_id)

    if as_json:
        print(json.dumps({
            "user": user_id, "state": state, "missing": missing,
            "points_total": n, "points_touched": touched,
            "action": ("ask_background" if state != ONBOARD_READY
                       else "proceed"),
        }, ensure_ascii=False))
        return

    print(f"用户 {user_id}　状态：{state}")
    print("=" * 56)

    if state == ONBOARD_READY:
        print(f"\n档案已就绪：{n} 个知识点，其中 {touched} 个已触及。")
        last = max(str(meta.get("updated_at") or ""), latest) or "未知"
        print(f"上次更新：{last}")
        print("\n【下一步】直接进入正常流程，不要再问背景信息。")
        print("  · 用户提问 → python3 scripts/query.py --user %s --q \"...\"" % user_id)
        print("  · 查看档案 → python3 scripts/report.py --user %s" % user_id)
        if touched == 0:
            print("\n⚠️ 已触及 0 个：档案存在但没有任何推断分，"
                  "说明冷启动没真正生效。")
            print("  · 先按 references/expansion.md §0.7 联网检索该背景对应的知识体系，"
                  "再跑 expand_profile.py 灌入")
            print("  · 或重跑 init_profile.py 补一次静态推断")
        return

    if state == ONBOARD_NEW:
        print("\n这是新用户，还没有任何档案。")
    else:
        got = [lab for k, lab, _ in FIELDS if k not in missing]
        print(f"\n档案已存在但不完整。已有：{'、'.join(got) or '无'}")
        print(f"还缺：{'、'.join(dict((k, l) for k, l, _ in FIELDS)[m] for m in missing)}")

    print("\n【下一步】把下面这段话发给用户（原样使用，可微调语气）：")
    print("-" * 56)
    print(ask_script(missing))
    print("-" * 56)
    print("\n用户回答后执行：")
    print(f'  python3 scripts/init_profile.py --user {user_id} \\')
    print(f'      --edu "<学历>" --job "<职业>" --region "<区域>"')
    print("\n若用户明确跳过：")
    print(f'  python3 scripts/init_profile.py --user {user_id} --edu "未填" '
          f'--job "未填" --region "未填" --skip-onboarding')
    print("  （铺完整骨架、全部 0 分，后续对话中随问随补）")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--user", required=True)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    check(a.user, a.json)


if __name__ == "__main__":
    main()
