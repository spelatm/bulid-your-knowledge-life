#!/usr/bin/env python3
"""S3 迁移：把 `职业技能` 那 46 条（+ 3 条联网扩展）按「能被哪门课教」重挂。

**只改元数据（subject / course / domain / 切面 / 衰减档位），不碰任何分数与证据。**
幂等、支持 `--dry-run`，跑完会断言「raw 合计一字未变」。

分流依据见 `design/职业技能分流-mapping.md`；一句话原则：

> 一条知识点能挂到某门课上，它就是知识；挂不上，它就是方法/技能/流程，
> 该去切面、`skills/`、Playbook——但**不属于这里**，这里只负责改归属。

`职业技能` 这个 subject 因此消失（骨架文件已删）。技能在 `skills/`，
流程在 `templates/playbooks.md`，思维方式靠 `transferable` 切面被检索到。

用法：
    python3 scripts/migrate_s3.py --user default --dry-run
    python3 scripts/migrate_s3.py --user default
"""
import os
import sys
import argparse
import core

# 条目 → (学科, 课程)。顺序无关，键必须精确匹配知识点名。
MAP = {
    # 沟通表达：职场实务知识（「怎么讲」有结构可学）
    "结构化表达": ("商业与管理", "通用职场工具"),
    "书面沟通": ("商业与管理", "通用职场工具"),
    "倾听与提问": ("商业与管理", "通用职场工具"),
    "跨部门沟通": ("商业与管理", "通用职场工具"),
    "冲突处理": ("商业与管理", "通用职场工具"),
    "对外沟通与客户管理": ("商业与管理", "通用职场工具"),
    # 思维方式：它们本来各自有课可教，只是被塞进了「职业技能」
    "结构化拆解": ("计算机科学", "软件工程"),
    "第一性原理": ("人文社科", "哲学"),
    "批判性思维": ("人文社科", "哲学"),
    "逆向思维": ("人文社科", "哲学"),
    "系统思考": ("工程与技术", "通用工程方法"),
    "概率化思维": ("数学", "概率与统计"),
    "类比迁移": ("人文社科", "心理"),
    # 信息处理
    "信息检索": ("人文社科", "学习与信息素养"),
    "资料筛选与判别": ("人文社科", "学习与信息素养"),
    "快速阅读": ("人文社科", "学习与信息素养"),
    "笔记与知识整理": ("人文社科", "学习与信息素养"),
    "数据解读": ("数学", "概率与统计"),
    "图表制作": ("商业与管理", "通用职场工具"),
    # 执行与协作：流程方法，有项目管理课兜底
    "任务拆解与排期": ("商业与管理", "运营管理"),
    "优先级判断": ("商业与管理", "运营管理"),
    "复盘方法": ("商业与管理", "运营管理"),
    "风险管理": ("商业与管理", "运营管理"),
    "会议组织": ("商业与管理", "通用职场工具"),
    "文档沉淀": ("商业与管理", "通用职场工具"),
    "协作工具链": ("商业与管理", "通用职场工具"),
    # 职业素养
    "行业认知": ("商业与管理", "战略"),
    "职业路径规划": ("商业与管理", "人力"),
    "简历与面试": ("商业与管理", "人力"),
    "mentor 与带人": ("商业与管理", "人力"),
    "职场礼仪": ("商业与管理", "通用职场工具"),
    "时间精力管理": ("商业与管理", "通用职场工具"),
    "压力管理": ("人文社科", "心理"),
    # 工具与平台
    "办公套件": ("商业与管理", "通用职场工具"),
    "协作平台": ("商业与管理", "通用职场工具"),
    "AI 工具使用": ("计算机科学", "人工智能"),
    "自动化脚本": ("计算机科学", "编程语言基础"),
    # 生活技能：语境是生活，知识本身可命题
    "基础财务规划": ("生活常识", "理财"),
    "法律常识": ("生活常识", "法律"),
    "健康与运动常识": ("生活常识", "健康"),
    "急救常识": ("生活常识", "急救"),
    "烹饪": ("生活常识", "饮食"),
    "出行与旅行规划": ("生活常识", "出行"),
    "家电与日常维修": ("生活常识", "生活维修"),
    # 联网扩展出来的学术素养（原挂在「职业技能 / 学术研究」下，同属错挂）
    "学术论文写作": ("人文社科", "教育与传播"),
    "科研伦理与学术规范": ("人文社科", "教育与传播"),
    "工程伦理": ("工程与技术", "通用工程方法"),
}

# 操作类用 tooling（不用就忘），其余保持 foundation
TOOLING_COURSES = {("生活常识", "饮食"), ("生活常识", "生活维修")}


def run(user_id, dry=False):
    udir = core.user_dir(user_id)
    if not os.path.isdir(udir):
        return f"用户 {user_id} 不存在", 1
    pdir = os.path.join(udir, "points")
    idx = core.index_points(udir)
    total_before = sum(float(m.get("raw_score", 0) or 0)
                       for _p, m, _b in idx["items"])

    moved, same, unknown = [], [], []
    for path, meta, body in idx["items"]:
        if str(meta.get("subject")) != "职业技能":
            continue
        name = str(meta.get("name", ""))
        dest = MAP.get(name)
        if not dest:
            same.append(name)      # 映射表没覆盖：不动，报出来
            continue
        subject, course = dest
        probe = {"subject": subject, "course": course, "name": name,
                 "raw_score": float(meta.get("raw_score", 0) or 0)}
        new = {
            "subject": subject, "course": course,
            "domain": core.domain_of(subject, course),
            "transferable": core.facet_of(probe, "transferable"),
            "context": core.facet_of(probe, "context"),
            "profile": ("tooling" if (subject, course) in TOOLING_COURSES
                        else meta.get("profile", "foundation")),
        }
        moved.append((name, meta.get("subject"), meta.get("course"),
                      subject, course, new["domain"]))
        if dry:
            continue
        meta.update(new)
        # 路径：名字没被别的文件占用时，文件名就该是纯知识点名。
        # 不能直接调 point_path——它会把「文件自己现在的路径」当撞名，
        # 结果所有文件都被改成「名字（学科）」（3.5.0 首跑踩过这个坑）。
        plain = os.path.join(pdir, core.safe_name(name) + ".md")
        if os.path.abspath(path) != os.path.abspath(plain) and not os.path.exists(plain):
            os.rename(path, plain)
            target = plain
        else:
            target = path
        core.write_md(target, meta, body)

    # 顺手把预置技能簇铺上（熟练度 0，不产生任何分数）
    seeded = ""
    if not dry:
        import skill
        seeded = skill.seed(udir)

    total_after = total_before
    if not dry:
        after = core.index_points(udir)
        total_after = sum(float(m.get("raw_score", 0) or 0)
                          for _p, m, _b in after["items"])

    out = [f"S3 职业技能分流 · 用户 {user_id}"
           f"{'（试运行，未落盘）' if dry else ''}",
           f"重挂 {len(moved)} 条，映射表未覆盖 {len(same)} 条，"
           f"raw 合计 {total_before:.1f} → {total_after:.1f}"]
    for name, s0, c0, s1, c1, dom in moved:
        out.append(f"  · {name}：{s0}/{c0} → {s1}/{c1}（{dom or '未归类'}）")
    if same:
        out.append(f"未覆盖（保持原样，需补映射）：{'、'.join(same)}")
    if seeded:
        out.append(seeded)
    if not dry and abs(total_after - total_before) > 0.05:
        out.append("⚠ 分数合计发生变化——这不是预期的，请检查")
        return "\n".join(out), 2
    return "\n".join(out), 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    text, code = run(a.user, a.dry_run)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
