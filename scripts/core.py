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


# ---------- 按 id / 名称取址（文件名已可读，不能再拼 id.md） ----------

def _scan(directory, prefix):
    """扫一个轨目录，返回 [(path, meta, body)]。"""
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.md"))):
        meta, body = read_md(path)
        if meta.get("id"):
            out.append((path, meta, body))
    return out


# 进程内索引缓存。为什么需要：一次 `--suggest` 里 add_edge 会对每一对边
# 重新取址，逐条重扫全库是 O(边数 × 知识点数) 次读盘。
# 失效条件是**目录 mtime + 文件数**——新增/改名/删除会变；
# 只改内容不变。调用方若就地修改 meta（add_edge 就是这么做的），
# 缓存里是同一批 dict，不会有陈旧问题。
_INDEX_CACHE = {}


def _sig(directory):
    try:
        return (os.stat(directory).st_mtime_ns, len(os.listdir(directory)))
    except OSError:
        return None


def invalidate(udir=None):
    """丢掉索引缓存。**写完内容后要调**——目录 mtime 只反映增删改名，

    改内容（改分、改 related）不会让签名变化，同进程里再读就会拿到旧 meta。
    跨进程调用不受影响（缓存不落盘）。
    """
    if udir is None:
        _INDEX_CACHE.clear()
        return
    prefix = os.path.abspath(udir)
    for k in [k for k in _INDEX_CACHE if k[0].startswith(prefix)]:
        _INDEX_CACHE.pop(k, None)


def _cached_index(udir, subdir, prefix):
    directory = os.path.join(udir, subdir) if subdir else udir
    key = (os.path.abspath(directory), prefix)
    sig = _sig(directory)
    hit = _INDEX_CACHE.get(key)
    if hit and sig is not None and hit[0] == sig:
        return hit[1]
    items = _scan(directory, prefix)
    by_id = {str(m["id"]): (p, m, b) for p, m, b in items}
    by_name = {}
    for p, m, b in items:
        by_name.setdefault(str(m.get("name", "")), (p, m, b))
    idx = {"by_id": by_id, "by_name": by_name, "items": items}
    if sig is not None:
        _INDEX_CACHE[key] = (sig, idx)
    return idx


def index_points(udir):
    """建立 {id: (path, meta, body)} 与 {name: (path, meta, body)} 双索引。

    自 3.4.0 起文件名 = 知识点名，`points/<id>.md` 已不存在。
    脚本一律走本索引，不拼文件名——这也是「id 以 frontmatter 为准」的落点。
    """
    return _cached_index(udir, "points", "kp")


def find_point(udir, key, index=None):
    """按 id、名称或文件名主干取一条知识点。返回 (path, meta, body) 或 None。

    文件主干也接受，是因为用户和 agent 都习惯顺手说文件名；
    但匹配的仍然是 frontmatter 的 name，不是碰运气。

    不传 `index` 时先走**单文件快路径**（文件名就是知识点名），
    命中就只读一个文件——查一条不该等于全库扫描。
    """
    key = str(key or "").strip()
    if not key:
        return None
    if index is None:
        cand = os.path.join(udir, "points", safe_name(key) + ".md")
        if os.path.exists(cand):
            meta, body = read_md(cand)
            if key in (str(meta.get("id")), str(meta.get("name"))):
                return cand, meta, body
    idx = index or index_points(udir)
    if key in idx["by_id"]:
        return idx["by_id"][key]
    if key in idx["by_name"]:
        return idx["by_name"][key]
    stem = os.path.splitext(os.path.basename(key))[0]
    for p, m, b in idx["items"]:
        if os.path.splitext(os.path.basename(p))[0] == stem:
            return p, m, b
    return None


# ---------- 横向边：正文托管块 ----------
#
# 本体在 frontmatter 的 `related: [名字]`；正文这块是**派生展示**，
# 让 Obsidian 的图谱能看见边（frontmatter 的纯文本不会进图谱）。
# 只有 link.py 写这块，其它脚本原样保留正文。

REL_BEGIN = "<!-- related:start -->"
REL_END = "<!-- related:end -->"
_REL_PAT = re.compile(r"\n*" + re.escape(REL_BEGIN) + r".*?"
                      + re.escape(REL_END) + r"\n*", re.S)


def render_related(entries, title="关联"):
    """entries: [(名字, 文件名主干, 备注)] → 托管块文本。"""
    lines = [REL_BEGIN, "", f"## {title}", ""]
    for name, stem, note in entries:
        # 主干与名字不一致（撞名加过（学科）后缀）时用别名，链接才解析得到
        link = f"[[{stem}]]" if stem == name else f"[[{stem}|{name}]]"
        lines.append(f"- {link}" + (f"　{note}" if note else ""))
    lines += ["", REL_END]
    return "\n".join(lines)


def set_related(body, entries, title="关联"):
    """把托管块替换成 entries；entries 为空则整块移除。幂等。"""
    body = _REL_PAT.sub("\n", body or "").rstrip("\n")
    if not entries:
        return body + "\n" if body else ""
    return body + "\n\n" + render_related(entries, title) + "\n"


# ---------- 技能簇（预设目录 skills/*.md） ----------
#
# 技能不按学科组织——「复盘方法」属于哪个学科没有答案，所以它不进 graph/。
# 预设目录只给「能力簇 + 名称 + 种类」，`requires`（技能→知识点）留给
# agent 在具体用户档案里连，避免凭空造边。

KINDS = ("composite", "tacit")


def load_skill_catalog():
    """解析 skills/*.md，返回 [{cluster, name, kind}]。"""
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "skills", "*.md"))):
        fname = os.path.basename(path)[:-3]
        if fname.upper() == "README":
            continue
        cluster = fname
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("# ") and not s.startswith("##"):
                    cluster = s[2:].strip() or fname
                elif s.startswith("- "):
                    body = s[2:].strip()
                    km = re.search(r"〔(\w+)〕", body)
                    kind = km.group(1) if km else "composite"
                    name = re.sub(r"〔[^〕]*〕", "", body).strip()
                    name = re.sub(r"[⭐*]", "", name).split("（")[0].strip()
                    if name:
                        out.append({"cluster": cluster, "name": name,
                                    "kind": kind})
    return out


def index_skills(udir):
    """{id: (...)} / {name: (...)}，结构同 index_points。"""
    return _cached_index(udir, os.path.join("experience", "skills"), "sk")


def find_skill(udir, key, index=None):
    key = str(key or "").strip()
    if not key:
        return None
    if index is None:
        cand = os.path.join(udir, "experience", "skills",
                            safe_name(key) + ".md")
        if os.path.exists(cand):
            meta, body = read_md(cand)
            if key in (str(meta.get("id")), str(meta.get("name"))):
                return cand, meta, body
    idx = index or index_skills(udir)
    if key in idx["by_id"]:
        return idx["by_id"][key]
    if key in idx["by_name"]:
        return idx["by_name"][key]
    stem = os.path.splitext(os.path.basename(key))[0]
    for p, m, b in idx["items"]:
        if os.path.splitext(os.path.basename(p))[0] == stem:
            return p, m, b
    return None


def recompute_raw(ev_ids, udir):
    """按证据重算 raw（append-only 的对账函数）。

    两种证据，语义不同，必须分开：

    - **种子证据**（`role: seed`，冷启动 / 联网扩展）→ **直接赋值**，
      且只在 raw=0 时生效；否则两个 50 分的种子会叠加成 75，凭空造分。
    - **累加证据**（其余）→ 正向边际递减、负向乘系数，与 `ingest.py` 一致
      （第 i 条用 i 作为递减基数）。

    返回 (raw, 未找到的证据 id 列表)。
    """
    raw, missing = 0.0, []
    for i, ev_id in enumerate(ev_ids, 1):
        path = os.path.join(udir, "evidence", f"{ev_id}.md")
        if not os.path.exists(path):
            missing.append(ev_id)
            continue
        meta, _ = read_md(path)
        t = str(meta.get("type", ""))
        w = float(meta.get("weight", 0) or 0)
        conf = float(meta.get("confidence", 0) or 0)
        if is_seed(meta):
            if raw <= 0:
                raw = w
        elif t in NEGATIVE_TYPES:
            raw = raw * w
        else:
            raw = apply_evidence(raw, w, conf, i)
    return max(0.0, min(100.0, raw)), missing


SEED_WEIGHT_FLOOR = 20.0


def is_seed(ev_meta):
    """种子证据判定。

    新记录直接看 `role: seed`；3.5.0 之前的记录没有这个字段——
    按「推断类 + 权重 ≥20」识别（正常推断权重是个位数，见 weights.md），
    迁移脚本会把这个推断落成显式字段。
    """
    if str(ev_meta.get("role", "")).strip() == "seed":
        return True
    return (str(ev_meta.get("type", "")) in ("inferred", "web_inferred")
            and float(ev_meta.get("weight", 0) or 0) >= SEED_WEIGHT_FLOOR)


def write_seed_evidence(udir, target_id, score, note="", source_ref="",
                        occurred_at=None, ev_type="inferred",
                        target_ids=None):
    """写一条种子证据。`weight = 种子分`、`confidence = 1.0`、`role = seed`。

    置信度固定 1.0 不是「很确信」，而是「种子分本身就是结论，不再打折」——
    否则 stored raw 与「按证据重算」的结果对不上，审计链就断了。
    """
    ev_id = new_id("ev")
    write_md(
        os.path.join(udir, "evidence", f"{ev_id}.md"),
        {"id": ev_id, "target_type": "point", "target_id": str(target_id),
         "target_ids": target_ids or [str(target_id)],
         "type": ev_type, "weight": round(float(score), 1), "confidence": 1.0,
         "role": "seed", "direction": "positive", "coefficient": "",
         "occurred_at": occurred_at or TODAY.isoformat(),
         "source_ref": source_ref, "note": note},
    )
    return ev_id


def sync_score(path, meta, body, udir):
    """按证据重算 raw 并同步 current/peak/status/last_verified_at，然后落盘。"""
    ev_ids = meta.get("evidence_ids") or []
    if isinstance(ev_ids, str):
        ev_ids = [ev_ids] if ev_ids else []
    raw, _missing = recompute_raw(ev_ids, udir)
    peak = max(float(meta.get("peak_score", 0) or 0), raw)
    last = meta.get("last_verified_at") or None
    current, _ = apply_decay(raw, last, str(meta.get("profile", "foundation")))
    status, base = judge_status(raw, current, peak)
    meta.update({"raw_score": round(raw, 1), "current_score": round(current, 1),
                 "peak_score": round(peak, 1), "status": status})
    write_md(path, meta, body)
    return raw, current, status, base
