#!/usr/bin/env python3
"""给知识点补正文：铺结构、写详解、看还差哪些。

为什么要有这个脚本：知识点文件原先只有一个标题，点进去什么也没有。
分数是「你多强」，正文才是「这一条到底是什么」——两者都得在同一个文件里，
否则查一条知识等于翻两个地方。

四个动作：

    python3 enrich.py --user u001 --restructure      # 给缺结构的条目铺页面骨架
    python3 enrich.py --user u001 --queue --limit 10 # 看下一批该写哪些
    python3 enrich.py --user u001 --batch c.json     # 批量写内容
    python3 enrich.py --user u001 --stats            # 内容完整度

`--batch` 的输入是一个 JSON：{条目名: {summary, detail, pitfalls, lessons, source}}。
只覆盖传进来的章节，没传的保持原样——所以可以分几次写，也可以只补一节。

**内容边界**（这条别越界）：
- `详解 / 易错点 / 经验与判断` 写的是**关于知识本身的内容**，可以由 agent 撰写，
  但必须标 `content_source`（通用知识 / 联网 / 用户原话）
- `我的掌握 / 我的经历` 只能由证据长出来，脚本自动重算，**不许手填**
"""
import os
import re
import sys
import json
import argparse

import core


def _prio(meta):
    """待补优先级：碰过的先写，其次核心条目，最后是边缘条目。"""
    raw = float(meta.get("raw_score", 0) or 0)
    imp = float(meta.get("importance", 0) or 0)
    return (0 if raw > 0 else 1, -imp, -raw, str(meta.get("name", "")))


def _skeleton_rank():
    """骨架顺序：门类与学科按 `_meta/domains.md` §2 的表序，课程与条目按骨架文件顺序。

    为什么不用目录字典序：中文按码点排会得到「商业 → 人文 → 工程 → 信息」，
    读起来是乱的。§2 那张表是人定的教学顺序，拿它当序更讲得通。
    表里没有的学科（用户自建）排最后，不挤掉骨架条目。
    """
    cat_rank, subj_rank = {}, {}
    path = os.path.join(core.ROOT, "_meta", "domains.md")
    if os.path.exists(path):
        in_sec = False
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("## "):
                    in_sec = line.startswith("## 2.")
                    continue
                if not in_sec or not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 2 or cells[0].startswith("门类") \
                        or set(cells[0]) <= set("-: "):
                    continue
                cat = cells[0]
                cat_rank.setdefault(cat, len(cat_rank))
                for i, subj in enumerate(re.split(r"[・、,，]", cells[1])):
                    subj = subj.strip().strip("*")
                    if subj:
                        subj_rank.setdefault((cat, subj), (cat_rank[cat], i))
    order = {}
    for i, g in enumerate(core.parse_graph()):
        order.setdefault(g["name"],
                         (subj_rank.get((g["category"], g["subject"]), (99, 99)), i))
    return order


def restructure(udir, dry=False):
    """给缺「概要」的条目铺结构。已有的正文段落原样留在页首，不覆盖。"""
    done = skipped = 0
    for path, meta, body in core.index_points(udir)["items"]:
        if core.get_section(body, "概要").strip():
            skipped += 1
            continue
        new_body = core.refresh_body(udir, meta, body)
        new_body = core.add_log(new_body, f"{core.TODAY.isoformat()} 建立页面结构"
                                           "（详解待补；我的掌握与我的经历自动生成）")
        if not dry:
            core.write_md(path, meta, new_body)
        done += 1
    if not dry:
        core.invalidate(udir)
    return done, skipped


def _cur_summary(body):
    """取「概要」里的那一句 `> 一句话：…`，用来判断这次传的 summary 变没变。"""
    for line in core.get_section(body, "概要").splitlines():
        s = line.strip()
        if s.startswith(">"):
            return s.lstrip(">").strip().replace("一句话：", "", 1).strip()
    return ""


def apply_content(udir, name, item, dry=False):
    """写一条的内容。返回 (状态, 说明)。"""
    hit = core.find_point(udir, name)
    if not hit:
        return "miss", f"未找到知识点：{name}"
    path, meta, body = hit
    summary = item.get("summary", None)
    changed = False
    for key, title in (("detail", "详解"), ("pitfalls", "易错点"),
                       ("lessons", "经验与判断")):
        if key in item and core.get_section(body, title).strip() != str(item[key]).strip():
            body = core.set_section(body, title, item[key])
            changed = True
    if summary is not None and _cur_summary(body) != str(summary).strip():
        changed = True
    if not changed:
        return "skip", f"{meta.get('name')}（章节内容未变）"
    body = core.refresh_body(udir, meta, body, summary=summary)
    src = str(item.get("source") or "通用知识").strip()
    meta["content_source"] = src
    meta["content_updated_at"] = core.TODAY.isoformat()
    body = core.add_log(body, f"{core.TODAY.isoformat()} 补写"
                               f"{'、'.join(t for k, t in (('detail', '详解'), ('pitfalls', '易错点'), ('lessons', '经验与判断')) if k in item)}"
                               f"（来源：{src}）")
    if not dry:
        core.write_md(path, meta, body)
    return "ok", meta.get("name")


def merge_markdown(udir, name, md_text, source="通用知识", dry=False):
    """从一份 markdown 里按 `## 章节` 合并内容（agent 写完直接灌进来）。"""
    item = {"source": source}
    for title, key in (("详解", "detail"), ("易错点", "pitfalls"),
                       ("经验与判断", "lessons"), ("概要", "summary")):
        text = core.get_section(md_text, title)
        if text.strip():
            item[key] = text.strip()
    if len(item) == 1:
        return "miss", "文件里没有 详解 / 易错点 / 经验与判断 任何一节"
    return apply_content(udir, name, item, dry=dry)


def queue(udir, limit=10, only_missing=True, order="touch", course=None):
    """列出还没写详解的条目。

    order="touch"：碰过的先写（有分数、核心度高）
    order="skeleton"：按骨架顺序铺（门类 → 学科 → 课程 → 条目），
      与用户在 Obsidian 里打开骨架看到的前后一致
    course 只留某门课的条目——一门课一次写完，同课程条目能互相呼应
    """
    rank = _skeleton_rank() if order == "skeleton" else {}

    def key(meta):
        if order == "skeleton":
            return rank.get(str(meta.get("name")), ((99, 99), 10 ** 6)) \
                   + (str(meta.get("name")),)
        return _prio(meta)

    rows = []
    for path, meta, body in core.index_points(udir)["items"]:
        if course and str(meta.get("course")) != course:
            continue
        has = bool(core.get_section(body, "详解").strip())
        if only_missing and has:
            continue
        rows.append((key(meta), meta, has))
    rows.sort(key=lambda x: x[0])
    rows = rows[:limit]
    scope = f"{course} " if course else ""
    out = [f"待补 {len(rows)} 条（{scope}共 {len(core.index_points(udir)['items'])} 条知识点）"]
    for _p, meta, has in rows:
        flag = "有详解" if has else "空"
        out.append(f"  · {meta.get('name')}　[{meta.get('course')}·{flag}]"
                   f" {float(meta.get('raw_score', 0) or 0):.0f} 分")
    return "\n".join(out)


def stats(udir):
    pts = core.index_points(udir)["items"]
    total = len(pts)
    detail = sum(1 for _p, _m, b in pts if core.get_section(b, "详解").strip())
    summary = sum(1 for _p, _m, b in pts if core.get_section(b, "概要").strip())
    exp = sum(1 for _p, m, _b in pts
              if float(m.get("raw_score", 0) or 0) > 0)
    lines = [
        f"知识点 {total} 条",
        f"  有页面结构（概要）：{summary}",
        f"  有详解：{detail}（{detail / total * 100:.0f}%）",
        f"  有掌握与经历（有证据）：{exp}",
        f"  纯骨架（只有结构、没有详解）：{total - detail}",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--restructure", action="store_true", help="给缺结构的条目铺页面骨架")
    p.add_argument("--batch", help="JSON 文件：{条目名: {summary, detail, ...}}")
    p.add_argument("--name", help="单条写：配合 --md 使用")
    p.add_argument("--md", help="含 ## 详解 等章节的 markdown 文件")
    p.add_argument("--source", default="通用知识", help="内容来源，写进 frontmatter")
    p.add_argument("--queue", action="store_true", help="列出还没写详解的条目")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--order", choices=["touch", "skeleton"], default="touch",
                   help="touch=碰过的先写；skeleton=按骨架顺序铺")
    p.add_argument("--course", help="只处理某门课（配合 --queue）")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    udir = core.user_dir(a.user)
    if a.restructure:
        done, skipped = restructure(udir, a.dry_run)
        print(f"铺结构：新增 {done} 条，已有结构跳过 {skipped} 条"
              + ("（dry-run，未写盘）" if a.dry_run else ""))
    elif a.batch:
        with open(a.batch, encoding="utf-8") as f:
            data = json.load(f)
        ok = miss = skip = 0
        for name, item in data.items():
            status, msg = apply_content(udir, name, item, dry=a.dry_run)
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                miss += 1
                print("  ✗", msg)
        if not a.dry_run:
            core.invalidate(udir)
        print(f"写入 {ok} 条，跳过 {skip} 条（内容未变），未命中 {miss} 条")
    elif a.name and a.md:
        with open(a.md, encoding="utf-8") as f:
            text = f.read()
        status, msg = merge_markdown(udir, a.name, text, a.source, a.dry_run)
        print(("已写入：" if status == "ok" else "失败：") + str(msg))
        if status == "ok" and not a.dry_run:
            core.invalidate(udir)
    elif a.queue:
        print(queue(udir, a.limit, order=a.order, course=a.course))
    elif a.stats:
        print(stats(udir))
    else:
        p.error("需要动作：--restructure / --batch / --queue / --stats")


if __name__ == "__main__":
    main()
