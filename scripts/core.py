#!/usr/bin/env python3
"""知识量化核心库：分数计算、状态判定、档案读写。

所有脚本共用此模块。配置全部来自 _meta/，改配置不改代码。
"""
import os
import re
import glob
import math
import hashlib
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today()


# ---------- 配置加载 ----------

def _load_pairs(path):
    """从 markdown 表格中抽取 (key, value) 对。

    兼容两种表头：`类型` 说明 | 数值 | …   以及  类型 | 数值 | …
    数值允许带 × 前缀（负向系数）。
    """
    pairs = {}
    if not os.path.exists(path):
        return pairs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            m = re.match(r"`([^`]+)`", cells[0])
            key = m.group(1) if m else cells[0].split()[0] if cells[0] else ""
            num = re.search(r"([\d.]+)", cells[1].replace("×", ""))
            if key and num:
                pairs[key] = float(num.group(1))
    return pairs


NEGATIVE_TYPES = ("forgot", "selftest_fail", "rusty_asked")


def load_weights():
    """返回 {证据类型: (权重或系数, 默认置信度)}。

    正向取「权重」列，置信度取第三列；负向取「系数」列。
    """
    out, confs = {}, {}
    path = os.path.join(ROOT, "_meta", "weights.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 2:
                    continue
                m = re.match(r"`([^`]+)`", cells[0])
                if not m:
                    continue
                key = m.group(1)
                num = re.search(r"([\d.]+)", cells[1].replace("×", ""))
                if not num:
                    continue
                out[key] = float(num.group(1))
                # 第三列可能是置信度（正向）或触发条件（负向）
                if len(cells) > 2:
                    c = re.match(r"^(0?\.\d+|1\.0)$", cells[2])
                    if c:
                        confs[key] = float(c.group(1))
    for k in list(out):
        out[k] = (out[k], confs.get(k, 1.0 if k in NEGATIVE_TYPES else 0.8))
    # 兜底：确保负向证据存在
    out.setdefault("forgot", (0.85, 1.0))
    out.setdefault("selftest_fail", (0.92, 1.0))
    out.setdefault("rusty_asked", (0.90, 1.0))
    return out


def load_half_life():
    """返回 {档位: 半衰期天数}"""
    hl = {"volatile": 45.0, "tooling": 90.0, "foundation": 180.0,
          "methodology": 365.0, "permanent": float("inf")}
    path = os.path.join(ROOT, "_meta", "decay_profiles.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\|\s*`(\w+)`\s*\|\s*([\d.]+|∞)\s*天?\s*\|", line)
                if m:
                    hl[m.group(1)] = (float("inf") if m.group(2) == "∞"
                                      else float(m.group(2)))
    return hl


# ---------- 计算 ----------

def apply_evidence(raw_score, w, confidence, ev_count=0):
    """正向证据累积，边际递减。

    raw += (100 - raw) * (w/100) * confidence
    同一知识点证据超过 5 条后，新增权重按 1/n 递减。
    """
    if ev_count > 5:
        w = w / (ev_count - 4)
    return min(100.0, raw_score + (100.0 - raw_score) * (w / 100.0) * confidence)


def apply_decay(raw_score, last_verified_at, profile="foundation"):
    """时间衰减：current = raw * 0.5^(Δt / half_life)"""
    hl = load_half_life().get(profile, 90.0)
    if hl == float("inf") or not last_verified_at:
        return raw_score, 0
    if isinstance(last_verified_at, str):
        last_verified_at = datetime.date.fromisoformat(last_verified_at)
    delta = (TODAY - last_verified_at).days
    if delta <= 0:
        return raw_score, 0
    return raw_score * (0.5 ** (delta / hl)), delta


def judge_status(raw, current, peak):
    """状态判定。rusty 与掌握等级可叠加展示。"""
    if raw <= 0:
        base = "untouched"
    elif current <= 25:
        base = "aware"
    elif current <= 50:
        base = "understood"
    elif current <= 75:
        base = "applicable"
    else:
        base = "proficient"
    if peak >= 40 and current <= peak * 0.6:
        return "rusty", base
    return base, base


LEVEL_LABEL = {
    "untouched": "未触及", "aware": "听说过", "understood": "理解原理",
    "applicable": "能上手做", "proficient": "精通", "rusty": "生疏了",
}


# ---------- 档案读写 ----------

def new_id(prefix):
    seed = f"{prefix}{datetime.datetime.now().isoformat()}{os.urandom(4).hex()}"
    return f"{prefix}_{hashlib.md5(seed.encode()).hexdigest()[:8]}"


def read_md(path):
    """解析 YAML frontmatter，返回 (meta_dict, body)。轻量实现，不依赖 yaml 库。"""
    if not os.path.exists(path):
        return {}, ""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta, body = {}, m.group(2)
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        elif v in ("true", "false"):
            v = (v == "true")
        else:
            try:
                v = float(v) if "." in v else int(v)
            except ValueError:
                v = v.strip("'\"")
        meta[k] = v
    return meta, body


def write_md(path, meta, body=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            v = "[" + ", ".join(str(x) for x in v) + "]"
        elif isinstance(v, bool):
            v = "true" if v else "false"
        lines.append(f"{k}: {v}")
    lines.append("---")
    # body 前导空行归一化：否则每次重写都会多累积几行（幂等性要求）
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n" + body.lstrip("\n"))


def parse_graph(subjects=None):
    """解析 graph/ 下的学科骨架，返回知识点列表。

    每项：{subject, course, name, importance, profile}
    重要性：⭐⭐=1.0（核心）/ ⭐=0.6（一般）/ 无星=0.3（边缘）
    """
    gdir = os.path.join(ROOT, "graph")
    out = []
    subject, course, default_profile = "", "", "foundation"
    for path in sorted(glob.glob(os.path.join(gdir, "*.md"))):
        fname = os.path.basename(path)[:-3]
        if fname == "README":
            continue
        with open(path, encoding="utf-8") as f:
            subject, course, default_profile = fname, "", "foundation"
            for line in f:
                s = line.strip()
                if s.startswith("# ") and not s.startswith("##"):
                    subject = s[2:].strip() or fname
                    course, default_profile = "", "foundation"
                    dm = re.search(r"`(\w+)`", s)
                    if dm:
                        default_profile = dm.group(1)
                elif s.startswith("## "):
                    course = s[3:].strip()
                elif s.startswith("### "):
                    course = s[4:].strip()
                elif s.startswith("- ") and "→" not in s:
                    if subjects and subject not in subjects:
                        continue
                    body = s[2:].strip()
                    pm = re.search(r"〔(\w+)〕", body)
                    profile = pm.group(1) if pm else default_profile
                    stars = body.count("⭐") or body.count("*")
                    name = re.sub(r"[⭐*]", "",
                                  re.split(r"[（(〔]", body)[0]).strip()
                    if not name:
                        continue
                    # 别名：让推断模板的命名也能命中骨架
                    am = re.search(r"[（(](?:又称|别名)[：:]?\s*([^）)]+)[）)]", body)
                    aliases = ([x.strip() for x in re.split(r"[、,，]", am.group(1))]
                               if am else [])
                    out.append({
                        "subject": subject, "course": course, "name": name,
                        "profile": profile, "aliases": aliases,
                        "importance": 1.0 if stars >= 2 else (0.6 if stars == 1 else 0.3),
                    })
    return out


def user_dir(user_id):
    return os.path.join(ROOT, "users", user_id)


# ---------- 域 / 切面 / 先验 配置（_meta/domains.md） ----------
#
# 伞层（域）只作导航与聚合，永不参与评分。切面与先验都是**启发值**。
# 配置全部来自 _meta/domains.md 的表格——改数值不改代码。

_OR_SEP = r"[｜|,，]"
_ZONE_CACHE = None


def _sections(text):
    """按 ## / ### 标题把文档切成 {标题: [行, ...]}。"""
    sec, out = None, {}
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.*)$", line)
        if m:
            sec = m.group(1).strip()
            out.setdefault(sec, [])
        elif sec is not None:
            out[sec].append(line)
    return out


def _rows(lines):
    """从若干行里抽出表格数据行（去掉表头与对齐分隔行）。"""
    out = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if all(c and set(c) <= set("-: ") for c in cells):
            continue
        if cells[0] in ("域", "学科", "匹配规则", "#"):
            continue
        out.append(cells)
    return out


def load_zone_config():
    """读取 _meta/domains.md，返回域 / 切面 / 先验配置（带缓存）。"""
    global _ZONE_CACHE
    if _ZONE_CACHE is not None:
        return _ZONE_CACHE
    cfg = {"domains": [], "subject_map": {}, "course_map": {},
           "facets": {"transferable": [], "context": []}, "prior": []}
    path = os.path.join(ROOT, "_meta", "domains.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            sec = _sections(f.read())

        def rows(prefix):
            for k, v in sec.items():
                if k.startswith(prefix):
                    return _rows(v)
            return []

        cfg["domains"] = [r[0] for r in rows("1.") if r[0]]
        for r in rows("2."):
            if len(r) >= 2 and r[1] not in ("——", "-", ""):
                cfg["subject_map"][r[0]] = r[1]
        for r in rows("3."):
            if len(r) >= 3 and r[2] not in ("——", "-", ""):
                cfg["course_map"][(r[0], r[1])] = r[2]

        def clean(s):
            """表格里的规则常用反引号包裹（`raw>0`），解析时剥掉。"""
            return s.strip().strip("`").strip()

        for r in rows("5.1"):
            if len(r) >= 2:
                cfg["facets"]["transferable"].append(
                    (clean(r[0]), float(clean(r[1]))))
        for r in rows("5.2"):
            if len(r) >= 2:
                cfg["facets"]["context"].append(
                    (clean(r[0]), [x.strip() for x in re.split(_OR_SEP, clean(r[1]))
                                   if x.strip()]))
        for r in rows("6."):
            if len(r) >= 2:
                cfg["prior"].append((clean(r[0]), clean(r[1])))
    _ZONE_CACHE = cfg
    return cfg


def domain_of(subject, course="", cfg=None):
    """课程级覆盖优先于学科默认；都没有则返回空串（表示「未归类」）。"""
    cfg = cfg or load_zone_config()
    return (cfg["course_map"].get((str(subject), str(course)))
            or cfg["subject_map"].get(str(subject), ""))


def _match_rule(rule, item, ctx=None):
    """判定一条配置规则是否命中。item 含 subject/course/name/raw_score。"""
    rule = rule.strip()
    if rule == "*":
        return True
    if rule == "raw>0":
        return float(item.get("raw_score", 0) or 0) > 0
    if rule.startswith("@"):
        return bool((ctx or {}).get(rule[1:]))
    for part in rule.split("&"):
        m = re.match(r"^(subject|course|name)\s*(=|~)\s*(.+)$", part.strip())
        if not m:
            return False
        field, op, val = m.group(1), m.group(2), m.group(3)
        have = str(item.get(field, "") or "")
        if op == "=":
            if have != val:
                return False
        elif not any(v in have for v in re.split(_OR_SEP, val) if v):
            return False
    return True


def facet_of(item, field, cfg=None):
    """按 _meta/domains.md §5 的规则自上而下求切面值，命中即停。"""
    cfg = cfg or load_zone_config()
    for rule, val in cfg["facets"].get(field, []):
        if _match_rule(rule, item):
            return list(val) if isinstance(val, list) else val
    return None


def prior_of(item, ctx=None, cfg=None):
    """按 §6 规则求先验档位（high / medium / low / minimal）。永不参与算分。"""
    cfg = cfg or load_zone_config()
    for rule, val in cfg["prior"]:
        if _match_rule(rule, item, ctx):
            return val
    return "minimal"


# ---------- 可读文件名 ----------

ILLEGAL_CHARS = {"\\": "＼", "/": "／", ":": "：", "*": "＊",
                 "?": "？", '"': "＂", "<": "＜", ">": "＞", "|": "｜"}
NAME_MAXLEN = 60


def safe_name(name, suffix=""):
    """把知识点名转成跨平台安全的文件名（不含扩展名）。

    `/ \\ : * ? " < > |` 换成全角——这些在 macOS/Linux 可用但在 Windows/SMB
    共享上会失败。末尾句点会被 Windows 截断，一并去掉。
    """
    n = re.sub(r"\s+", " ", str(name or "")).strip().rstrip(".")
    for k, v in ILLEGAL_CHARS.items():
        n = n.replace(k, v)
    if suffix:
        n = f"{n}（{suffix}）"
    if len(n) > NAME_MAXLEN:
        n = n[:NAME_MAXLEN - 1] + "…"
    return n or "未命名"


def unique_path(directory, stem, ext=".md"):
    """在 directory 下为 stem 找一个不冲突的路径：撞名则追加 -2 / -3…"""
    path = os.path.join(directory, stem + ext)
    i = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{stem}-{i}{ext}")
        i += 1
    return path


def point_path(pdir, name, subject=""):
    """知识点落盘路径：可读名优先 → 撞名加（学科）后缀 → 再撞加序号。

    与 migrate_s1.py 的消歧规则保持一致，否则新老条目的命名会不统一。
    """
    p = os.path.join(pdir, safe_name(name) + ".md")
    if not os.path.exists(p):
        return p
    if subject:
        p2 = os.path.join(pdir, safe_name(name, subject) + ".md")
        if not os.path.exists(p2):
            return p2
    return unique_path(pdir, safe_name(name, subject))
