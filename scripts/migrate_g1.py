"""G1 迁移：graph/ 由「9 个学科文件」重组成「门类 / 学科 / 课程」三层。

对应 `design/graph重构与学科粒度.md`。两个动作：

  1. `--tree`   写出新骨架（11 门类目录 / 37 学科目录 / 69 课程索引文件）
  2. `--points` 给已有知识点回填 `category` / `subject` / `course`

设计要点（来自用户 2026-10-23 的定案）：
  · 中间层可建文件，但只装结构；知识点只在叶节点文件里
  · 课程索引带 frontmatter（category/subject/course/profile），路径只是阅读用的
  · 跨课程不复制，靠 `related` 连边

安全约束：
  · 不动 `raw_score` / `evidence_ids` / `relevance`，只改归属字段
  · 不回填 `profile`——骨架档位是新的、正确的，但改它会改变衰减结果，
    那是另一个决策（见 CHANGELOG 3.8.0「未做」）
  · 幂等：重复跑只输出「已存在 / 0 条」
  · `--dry-run` 只报告，不落盘

用法：
  python3 scripts/migrate_g1.py --dry-run
  python3 scripts/migrate_g1.py --tree
  python3 scripts/migrate_g1.py --points
"""
import argparse
import collections
import glob
import os
import re
import sys

import core

# ---------- 课程映射：(旧学科, 旧课程) -> (门类, 新学科, 新课程) ----------
# 65 门课 1:1 平移；另外 2 门（政治与法律、教育与传播）在 SPLIT 里逐条判定。
MAP = {
    # 信息与计算技术
    ("计算机科学", "编程语言基础"): ("信息与计算技术", "计算机科学与技术", "编程语言基础"),
    ("计算机科学", "数据结构与算法"): ("信息与计算技术", "计算机科学与技术", "数据结构与算法"),
    ("计算机科学", "计算机系统"): ("信息与计算技术", "计算机科学与技术", "计算机系统"),
    ("计算机科学", "操作系统进阶"): ("信息与计算技术", "计算机科学与技术", "操作系统进阶"),
    ("计算机科学", "计算机网络"): ("信息与计算技术", "计算机科学与技术", "计算机网络"),
    ("计算机科学", "数据库"): ("信息与计算技术", "计算机科学与技术", "数据库"),
    ("计算机科学", "编译原理"): ("信息与计算技术", "计算机科学与技术", "编译原理"),
    ("计算机科学", "软件工程"): ("信息与计算技术", "软件工程", "软件工程"),
    ("计算机科学", "分布式与架构"): ("信息与计算技术", "软件工程", "分布式与架构"),
    ("计算机科学", "前端"): ("信息与计算技术", "软件工程", "前端"),
    ("计算机科学", "人工智能"): ("信息与计算技术", "人工智能", "人工智能"),
    ("计算机科学", "安全"): ("信息与计算技术", "网络空间安全", "安全"),
    # 自然科学与数学
    ("数学", "基础数学（中小学）"): ("自然科学与数学", "数学", "基础数学（中小学）"),
    ("数学", "代数"): ("自然科学与数学", "数学", "代数"),
    ("数学", "数学分析"): ("自然科学与数学", "数学", "数学分析"),
    ("数学", "概率与统计"): ("自然科学与数学", "数学", "概率与统计"),
    ("数学", "离散数学"): ("自然科学与数学", "数学", "离散数学"),
    ("数学", "数值与优化"): ("自然科学与数学", "数学", "数值与优化"),
    ("数学", "应用方向"): ("自然科学与数学", "数学", "应用方向"),
    ("自然科学", "力学"): ("自然科学与数学", "物理学", "力学"),
    ("自然科学", "热学"): ("自然科学与数学", "物理学", "热学"),
    ("自然科学", "电磁学"): ("自然科学与数学", "物理学", "电磁学"),
    ("自然科学", "近代物理"): ("自然科学与数学", "物理学", "近代物理"),
    ("自然科学", "实验方法"): ("自然科学与数学", "物理学", "实验方法"),
    ("自然科学", "反应原理"): ("自然科学与数学", "化学", "反应原理"),
    ("自然科学", "分支"): ("自然科学与数学", "化学", "分支"),
    ("自然科学", "遗传与进化"): ("自然科学与数学", "生物学", "遗传与进化"),
    ("自然科学", "个体与群体"): ("自然科学与数学", "生物学", "个体与群体"),
    ("自然科学", "实验"): ("自然科学与数学", "生物学", "实验"),
    # 工程、制造与建造
    ("工程与技术", "机械"): ("工程、制造与建造", "机械工程", "机械"),
    ("工程与技术", "电子信息"): ("工程、制造与建造", "电子信息工程", "电子信息"),
    ("工程与技术", "土木与建筑"): ("工程、制造与建造", "土木工程", "土木与建筑"),
    ("工程与技术", "材料"): ("工程、制造与建造", "材料科学与工程", "材料"),
    ("工程与技术", "化工"): ("工程、制造与建造", "化学工程与技术", "化工"),
    ("工程与技术", "自动化与控制"): ("工程、制造与建造", "控制科学与工程", "自动化与控制"),
    ("工程与技术", "通用工程方法"): ("工程、制造与建造", "工程方法论", "通用工程方法"),
    # 商业、管理与法律
    ("商业与管理", "管理学基础"): ("商业、管理与法律", "工商管理", "管理学基础"),
    ("商业与管理", "战略"): ("商业、管理与法律", "工商管理", "战略"),
    ("商业与管理", "运营管理"): ("商业、管理与法律", "工商管理", "运营管理"),
    ("商业与管理", "人力"): ("商业、管理与法律", "工商管理", "人力"),
    ("商业与管理", "营销"): ("商业、管理与法律", "市场营销", "营销"),
    ("商业与管理", "财务与会计"): ("商业、管理与法律", "会计学", "财务与会计"),
    ("商业与管理", "创业与商业"): ("商业、管理与法律", "创业学", "创业与商业"),
    ("商业与管理", "通用职场工具"): ("商业、管理与法律", "职场实务", "通用职场工具"),
    ("人文社科", "经济"): ("商业、管理与法律", "经济学", "经济"),
    ("人文社科", "金融与会计"): ("商业、管理与法律", "金融学", "金融与会计"),
    # 人文与艺术
    ("人文社科", "哲学"): ("人文与艺术", "哲学", "哲学"),
    ("人文社科", "历史"): ("人文与艺术", "历史学", "历史"),
    ("外语", "词汇"): ("人文与艺术", "外国语言文学", "词汇"),
    ("外语", "语法"): ("人文与艺术", "外国语言文学", "语法"),
    ("外语", "听力"): ("人文与艺术", "外国语言文学", "听力"),
    ("外语", "口语"): ("人文与艺术", "外国语言文学", "口语"),
    ("外语", "阅读"): ("人文与艺术", "外国语言文学", "阅读"),
    ("外语", "写作"): ("人文与艺术", "外国语言文学", "写作"),
    ("外语", "应用能力"): ("人文与艺术", "外国语言文学", "应用能力"),
    ("艺术与设计", "视觉基础"): ("人文与艺术", "设计学", "视觉基础"),
    ("艺术与设计", "设计方法论"): ("人文与艺术", "设计学", "设计方法论"),
    ("艺术与设计", "数字设计工具"): ("人文与艺术", "设计学", "数字设计工具"),
    ("艺术与设计", "音乐"): ("人文与艺术", "音乐与舞蹈学", "音乐"),
    ("艺术与设计", "影视与摄影"): ("人文与艺术", "戏剧与影视学", "影视与摄影"),
    ("艺术与设计", "艺术史与批评"): ("人文与艺术", "艺术学理论", "艺术史与批评"),
    ("艺术与设计", "创作素养"): ("人文与艺术", "艺术学理论", "创作素养"),
    # 社会科学与信息
    ("人文社科", "社会"): ("社会科学与信息", "社会学", "社会"),
    ("人文社科", "心理"): ("社会科学与信息", "心理学", "心理"),
    ("人文社科", "学习与信息素养"): ("社会科学与信息", "图书情报与档案管理", "学习与信息素养"),
    # 生活常识（第 11 个门类，非 ISCED-F）
    ("生活常识", "理财"): ("生活常识", "生活实务", "理财"),
    ("生活常识", "法律"): ("生活常识", "生活实务", "法律"),
    ("生活常识", "健康"): ("生活常识", "生活实务", "健康"),
    ("生活常识", "急救"): ("生活常识", "生活实务", "急救"),
    ("生活常识", "饮食"): ("生活常识", "生活实务", "饮食"),
    ("生活常识", "出行"): ("生活常识", "生活实务", "出行"),
    ("生活常识", "生活维修"): ("生活常识", "生活实务", "生活维修"),
}

# 需要逐条判定的两门课（共 14 条）
SPLIT = {
    ("人文社科", "政治与法律", "政治制度比较"): ("社会科学与信息", "政治学", "政治学"),
    ("人文社科", "政治与法律", "国际关系理论"): ("社会科学与信息", "政治学", "政治学"),
    ("人文社科", "政治与法律", "公共政策分析"): ("社会科学与信息", "政治学", "政治学"),
    ("人文社科", "政治与法律", "宪法与基本权利"): ("社会科学与信息", "法学", "法学"),
    ("人文社科", "政治与法律", "民法基础"): ("社会科学与信息", "法学", "法学"),
    ("人文社科", "政治与法律", "刑法基础"): ("社会科学与信息", "法学", "法学"),
    ("人文社科", "政治与法律", "行政法"): ("社会科学与信息", "法学", "法学"),
    ("人文社科", "教育与传播", "学习理论"): ("教育", "教育学", "教育学原理"),
    ("人文社科", "教育与传播", "教学设计"): ("教育", "教育学", "教育学原理"),
    ("人文社科", "教育与传播", "教育测量与评价"): ("教育", "教育学", "教育学原理"),
    ("人文社科", "教育与传播", "传播学理论"): ("社会科学与信息", "新闻传播学", "传播学"),
    ("人文社科", "教育与传播", "媒介与舆论"): ("社会科学与信息", "新闻传播学", "传播学"),
    ("人文社科", "教育与传播", "学术论文写作"): ("社会科学与信息", "图书情报与档案管理", "学习与信息素养"),
    ("人文社科", "教育与传播", "科研伦理与学术规范"): ("社会科学与信息", "图书情报与档案管理", "学习与信息素养"),
}

# 同名课程消歧：旧骨架里「基础」在化学、生物下各有一份，靠父标题区分，
# 迁移时顺手改名（`化学基础` / `生物学基础`），否则新树里两门课同名。
PARENT_MAP = {
    ("自然科学", "化学", "基础"): ("自然科学与数学", "化学", "化学基础"),
    ("自然科学", "生物", "基础"): ("自然科学与数学", "生物学", "生物学基础"),
}

# 课程默认衰减档位。**这是重新定的，不是从旧文件继承的**——
# 旧 `parse_graph` 只在 `# 学科名` 那一行找反引号，而档位写在第三行的说明句里，
# 所以所有学科默认值都退化成 foundation（外语本该 volatile、商业本该 methodology）。
PROFILE = {
    ("人文与艺术", "外国语言文学", "词汇"): "volatile",
    ("人文与艺术", "外国语言文学", "语法"): "volatile",
    ("人文与艺术", "外国语言文学", "听力"): "tooling",
    ("人文与艺术", "外国语言文学", "口语"): "tooling",
    ("人文与艺术", "外国语言文学", "阅读"): "tooling",
    ("人文与艺术", "外国语言文学", "写作"): "tooling",
    ("人文与艺术", "外国语言文学", "应用能力"): "tooling",
    ("人文与艺术", "历史学", "历史"): "tooling",
    ("人文与艺术", "设计学", "视觉基础"): "tooling",
    ("人文与艺术", "设计学", "设计方法论"): "methodology",
    ("人文与艺术", "设计学", "数字设计工具"): "tooling",
    ("人文与艺术", "音乐与舞蹈学", "音乐"): "tooling",
    ("人文与艺术", "戏剧与影视学", "影视与摄影"): "tooling",
    ("人文与艺术", "艺术学理论", "艺术史与批评"): "tooling",
    ("人文与艺术", "艺术学理论", "创作素养"): "methodology",
    ("人文与艺术", "哲学", "哲学"): "methodology",
    ("社会科学与信息", "法学", "法学"): "volatile",
    ("社会科学与信息", "政治学", "政治学"): "methodology",
    ("社会科学与信息", "社会学", "社会"): "methodology",
    ("社会科学与信息", "心理学", "心理"): "methodology",
    ("社会科学与信息", "新闻传播学", "传播学"): "methodology",
    ("社会科学与信息", "图书情报与档案管理", "学习与信息素养"): "tooling",
    ("教育", "教育学", "教育学原理"): "methodology",
    ("生活常识", "生活实务", "理财"): "methodology",
    ("生活常识", "生活实务", "法律"): "volatile",
    ("生活常识", "生活实务", "健康"): "foundation",
    ("生活常识", "生活实务", "急救"): "foundation",
    ("生活常识", "生活实务", "饮食"): "tooling",
    ("生活常识", "生活实务", "出行"): "tooling",
    ("生活常识", "生活实务", "生活维修"): "tooling",
}
# 商业、管理与法律 整域用 methodology（管理理论不掉，工具才掉）
for _k in list(MAP):
    _c, _s, _co = MAP[_k]
    if _c == "商业、管理与法律":
        PROFILE.setdefault((_c, _s, _co), "methodology")


def profile_of(triple):
    return PROFILE.get(triple, "foundation")


# ---------- 读旧骨架（保留逐条显式档位与别名） ----------

def load_old():
    """返回 [{subject, course, name, stars, profile, aliases, default}]。"""
    out = []
    gdir = os.path.join(core.ROOT, "graph")
    for path in sorted(glob.glob(os.path.join(gdir, "*.md"))):
        fname = os.path.basename(path)[:-3]
        if fname == "README":
            continue
        subject, course, h2, default = fname, "", "", "foundation"
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("# ") and not s.startswith("##"):
                    subject = s[2:].strip() or fname
                    continue
                if s.startswith("## "):
                    course = h2 = s[3:].strip()
                    continue
                if s.startswith("### "):
                    course = s[4:].strip()
                    continue
                if not s.startswith("- "):
                    continue
                body = s[2:].strip()
                if "→" in body:            # 「→ 见 xxx」引用行，不是实体
                    continue
                pm = re.search(r"〔(\w+)〕", body)
                am = re.search(r"[（(](?:又称|别名)[：:]?\s*([^）)]+)[）)]", body)
                aliases = ([x.strip() for x in re.split(r"[、,，]", am.group(1))]
                           if am else [])
                head = re.split(r"[（(〔]", body)[0]
                name = re.sub(r"[⭐*]", "", head).strip()
                if not name:
                    continue
                stars = body.count("⭐") or body.count("*")
                out.append({
                    "subject": subject, "course": course, "h2": h2, "name": name,
                    "stars": 2 if stars >= 2 else (1 if stars == 1 else 0),
                    "profile": pm.group(1) if pm else "",
                    "aliases": aliases,
                })
    return out


def route(item):
    """旧条目 -> (门类, 学科, 课程)；路由不到返回 None。"""
    key3 = (item["subject"], item["course"], item["name"])
    if key3 in SPLIT:
        return SPLIT[key3]
    parent = PARENT_MAP.get((item["subject"], item.get("h2", ""), item["course"]))
    if parent:
        return parent
    return MAP.get((item["subject"], item["course"]))


def render_name(item):
    stars = "⭐⭐" if item["stars"] >= 2 else ("⭐" if item["stars"] == 1 else "")
    tail = f"（又称 {'、'.join(item['aliases'])}）" if item["aliases"] else ""
    prof = f"〔{item['profile']}〕" if item["profile"] else ""
    return f"- {item['name']}{tail} {stars}{prof}".rstrip()


# ---------- 动作 1：写树 ----------

def write_tree(items, dry=False):
    groups = collections.OrderedDict()
    unmapped = []
    for it in items:
        t = route(it)
        if not t:
            unmapped.append(it)
            continue
        groups.setdefault(t, []).append(it)
    if unmapped:
        print(f"✗ {len(unmapped)} 条路由不到目标课程：")
        for it in unmapped[:10]:
            print(f"    {it['subject']} / {it['course']} / {it['name']}")
        sys.exit(1)

    made = 0
    for (cat, subj, course), rows in groups.items():
        d = os.path.join(core.ROOT, "graph", cat, subj)
        path = os.path.join(d, core.safe_name(course) + ".md")
        meta = {"category": cat, "subject": subj, "course": course,
                "profile": profile_of((cat, subj, course))}
        body = (f"# {course}\n\n> {cat} › {subj}\n\n"
                + "\n".join(render_name(r) for r in rows) + "\n")
        if dry:
            made += 1
            continue
        os.makedirs(d, exist_ok=True)
        core.write_md(path, meta, body)
        made += 1
    return groups, made


def drop_old_files(dry=False):
    """旧的三层扁平文件在树建好后删除；README 保留（会被重写）。"""
    old = [p for p in glob.glob(os.path.join(core.ROOT, "graph", "*.md"))
           if os.path.basename(p) != "README.md"]
    if not dry:
        for p in old:
            os.remove(p)
    return len(old)


# ---------- 动作 2：回填用户知识点 ----------

def build_lookup(items):
    """(旧学科, 旧课程, 名字) -> 新三元组。用于回填——同名课程（化学/生物的「基础」）
    只能靠名字区分，靠 (学科, 课程) 两元组会撞。"""
    out = {}
    for it in items:
        t = route(it)
        if t:
            out.setdefault((it["subject"], it["course"], it["name"]), t)
    return out


def backfill_points(udir, lookup, dry=False):
    idx = core.index_points(udir)["by_id"]
    changed = 0
    unmapped = []
    before_raw = sum(float(m.get("raw_score", 0) or 0) for _p, m, _b in idx.values())
    for path, meta, body in idx.values():
        key = (str(meta.get("subject", "")), str(meta.get("course", "")),
               str(meta.get("name", "")))
        t = lookup.get(key) or SPLIT.get(key) or MAP.get(key[:2])
        if key[0] == "自然科学" and key[1] == "基础":
            # 旧两元组不区分化学/生物，只能靠名字；查不到就别猜
            t = lookup.get(key)
        if not t:
            unmapped.append(key)
            continue
        cat, subj, course = t
        if (meta.get("category"), meta.get("subject"), meta.get("course")) == t:
            continue
        meta["category"], meta["subject"], meta["course"] = cat, subj, course
        if not dry:
            core.write_md(path, meta, body)
        changed += 1
    after_raw = sum(float(m.get("raw_score", 0) or 0) for _p, m, _b in idx.values())
    return changed, unmapped, before_raw, after_raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="default")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tree", action="store_true", help="只重写 graph/")
    ap.add_argument("--points", action="store_true", help="只回填知识点")
    a = ap.parse_args()
    dry = a.dry_run
    do_tree = a.tree or not (a.tree or a.points)
    do_points = a.points or not (a.tree or a.points)

    items = load_old()
    print(f"旧骨架：{len(items)} 条")

    if do_tree:
        groups, made = write_tree(items, dry)
        cats = {k[0] for k in groups}
        subs = {(k[0], k[1]) for k in groups}
        print(f"新骨架：{len(cats)} 门类 / {len(subs)} 学科 / {made} 课程索引 / "
              f"{sum(len(v) for v in groups.values())} 条")
        if not dry:
            n = drop_old_files()
            print(f"已删除旧扁平文件 {n} 个")

    if do_points:
        udir = core.user_dir(a.user)
        changed, unmapped, b, a2 = backfill_points(udir, build_lookup(items), dry)
        print(f"知识点：改动 {changed} 条，未映射 {len(unmapped)} 条")
        for k in unmapped[:10]:
            print(f"    未映射：{k}")
        print(f"raw 合计：{b:.1f} → {a2:.1f}"
              f"{'  ✓ 未变' if abs(b - a2) < 1e-9 else '  ✗ 变了，必须中止'}")
        if abs(b - a2) > 1e-9:
            sys.exit(2)

    if dry:
        print("（dry-run，未落盘）")


if __name__ == "__main__":
    main()
