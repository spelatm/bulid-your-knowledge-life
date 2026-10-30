#!/usr/bin/env python3
"""知识量化核心库：分数计算、状态判定、档案读写。

所有脚本共用此模块。配置全部来自 _meta/，改配置不改代码。
"""
import os
import re
import glob
import json
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


# 配置缓存。为什么要缓存：`apply_decay` 每条知识点都会调 `load_half_life()`，
# 而在这个运行环境里**每一次 open 都有固定开销（约 23ms）**——500 条就是 11 秒。
# 配置在一次进程里不会变，读一次就够。改 `_meta/` 后重开进程即生效。
_CFG = {}


def _cached(key, loader):
    if key not in _CFG:
        _CFG[key] = loader()
    return _CFG[key]


def load_weights():
    """返回 {证据类型: (权重或系数, 默认置信度)}。

    正向取「权重」列，置信度取第三列；负向取「系数」列。
    """
    return _cached("weights", _load_weights_raw)


def _load_weights_raw():
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
    return _cached("half_life", _load_half_life_raw)


def _load_half_life_raw():
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


def _parse_entries(text, category, subject, course, default_profile, subjects):
    """解析课程索引里的 `- 条目` 行。新旧两种骨架共用这一段。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("- ") or "→" in s:
            continue
        if subjects and subject not in subjects:
            continue
        body = s[2:].strip()
        pm = re.search(r"〔(\w+)〕", body)
        profile = pm.group(1) if pm else default_profile
        stars = body.count("⭐") or body.count("*")
        # 前置：`← A、B`（与 `→ 见 X` 的引用标记对称），写在「需要前置」的那条上
        pw = re.search(r"←\s*([^⭐〔（(]+)", body)
        prereq = ([x.strip() for x in re.split(r"[、,，]", pw.group(1))]
                  if pw else [])
        name = re.sub(r"[⭐*]", "",
                      re.split(r"[（(〔←]", body)[0]).strip()
        if not name:
            continue
        am = re.search(r"[（(](?:又称|别名)[：:]?\s*([^）)]+)[）)]", body)
        aliases = ([x.strip() for x in re.split(r"[、,，]", am.group(1))]
                   if am else [])
        out.append({
            "category": category, "subject": subject, "course": course,
            "name": name, "profile": profile, "aliases": aliases,
            "prerequisite": [x for x in prereq if x],
            "importance": 1.0 if stars >= 2 else (0.6 if stars == 1 else 0.3),
        })
    return out


def parse_graph(subjects=None):
    """解析 graph/ 骨架，返回知识点列表。

    两种布局都认：

      · **三层树**（3.8.0 起，推荐）：`graph/<门类>/<学科>/<课程>.md`，
        门类/学科/课程取自文件 frontmatter，路径只负责阅读
      · **扁平文件**（旧部署）：`graph/<学科>.md`，`#` 学科 / `##` 课程

    每项：{category, subject, course, name, importance, profile, aliases}
    重要性：⭐⭐=1.0（核心）/ ⭐=0.6（一般）/ 无星=0.3（边缘）
    """
    gdir = os.path.join(ROOT, "graph")
    deep = sorted(glob.glob(os.path.join(gdir, "*", "*", "*.md")))

    if deep:                                  # 三层树
        out = []
        for path in deep:
            rel = os.path.relpath(path, gdir).split(os.sep)
            meta, body = read_md(path)
            category = str(meta.get("category") or rel[0])
            subject = str(meta.get("subject") or rel[1])
            course = str(meta.get("course") or rel[2][:-3])
            prof = str(meta.get("profile") or "foundation")
            out.extend(_parse_entries(body, category, subject, course, prof,
                                      subjects))
        return out

    out = []                                  # 扁平文件（向后兼容）
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
                elif s.startswith("- "):
                    if subjects and subject not in subjects:
                        continue
                    out.extend(_parse_entries(
                        s, "", subject, course, default_profile, subjects))
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


# 落盘索引缓存。为什么需要：本机一次 open+read ≈ 24ms，500 条知识点就是 12 秒，
# 而 `query.py` 每次提问都要读全库——用户等不起，这也不是「检索性能高」该有的样子。
# 逐文件比对 (mtime_ns, size) 只花 stat 的时间（500 个约 0 秒），
# 只重读真正变化的文件，其余直接复用缓存里的 meta。
# 缓存是**派生数据**：删掉它只会让下一次慢一点，不会丢任何信息。
DISK_CACHE_VER = 1


def _cache_file(udir, prefix, subdir):
    slug = re.sub(r"[^0-9A-Za-z]+", "_", subdir or "root")
    return os.path.join(udir, ".cache", f"{prefix}-{slug}.json")


def _read_disk_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("v") == DISK_CACHE_VER and isinstance(data.get("files"), dict):
            return data["files"]
    except (OSError, ValueError):
        pass
    return {}


def _scan_cached(directory, prefix, cache_path):
    """按 mtime+size 复用上次解析结果，只重读变过的文件。"""
    old = _read_disk_cache(cache_path)
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".md"))
    except OSError:
        return []
    out, fresh, dirty = [], {}, False
    for name in names:
        path = os.path.join(directory, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        hit = old.get(name)
        if (hit and hit.get("mtime_ns") == st.st_mtime_ns
                and hit.get("size") == st.st_size):
            meta, body = hit.get("meta") or {}, hit.get("body") or ""
        else:
            try:
                meta, body = read_md(path)
            except (OSError, UnicodeDecodeError):
                continue
            dirty = True
        if not meta.get("id"):
            continue
        fresh[name] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size,
                       "meta": meta, "body": body}
        out.append((path, meta, body))
    if dirty or set(fresh) != set(old):
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            tmp = cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"v": DISK_CACHE_VER, "files": fresh}, f,
                          ensure_ascii=False, default=str)
            os.replace(tmp, cache_path)
        except OSError:
            pass          # 缓存写不进去不影响正确性，只是下次还慢
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
    items = _scan_cached(directory, prefix, _cache_file(udir, prefix, subdir))
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
    """entries: [(名字, 文件名主干, 备注)] → 只有托管块的正文（不含标题）。

    托管块**必须整块待在一个章节里**：开始/结束标记跨到别的章节上，
    章节拆分就会把它剪断（3.10.0 之前就是「标记在前、标题在后」，一重排就坏）。
    """
    lines = [REL_BEGIN, ""]
    for name, stem, note in entries:
        # 主干与名字不一致（撞名加过（学科）后缀）时用别名，链接才解析得到
        link = f"[[{stem}]]" if stem == name else f"[[{stem}|{name}]]"
        lines.append(f"- {link}" + (f"　{note}" if note else ""))
    lines += ["", REL_END]
    return "\n".join(lines)


def set_related(body, entries, title="关联"):
    """把「关联」章节整体替换成 entries；entries 为空则删掉该章节。幂等。

    先清掉散落在别处的孤儿标记——老档案里块是追加在文末的，
    章节重排后会把 `<!-- related:start -->` 留在「更新记录」里。
    """
    body = re.sub(r"^[ \t]*" + re.escape(REL_BEGIN) + r"[ \t]*$\n?", "", body or "", flags=re.M)
    body = re.sub(r"^[ \t]*" + re.escape(REL_END) + r"[ \t]*$\n?", "", body, flags=re.M)
    return set_section(body, title,
                       render_related(entries, title) if entries else "")


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
    """按证据重算 raw 并同步 current/peak/status/last_verified_at，然后落盘。

    顺手重算正文的自动块（我的掌握 / 我的经历）——否则分数变了、页面里写的
    还是旧数字，读到的人会以哪个为准都不知道。
    """
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
    try:
        body = refresh_body(udir, meta, body)
    except Exception:
        pass          # 正文结构出问题也不该挡住记账，下次 refresh 会补上
    write_md(path, meta, body)
    return raw, current, status, base


# ---------- 知识点正文：结构、自动块、索引 ----------
#
# 为什么正文要分「概览 / 详解 / 我的掌握 / 我的经历」：
# 一条知识点不是一张分数卡片，它得能回答四件事——**它是什么**（公共知识）、
# **我掌握到什么程度**（分数与证据）、**我在哪用过**（经历）、**我得出什么判断**（经验）。
# 前两类是骨架，后两类只能由证据长出来。
#
# 为什么概要必须是索引：概要写死一段话，一改详解就会漂。所以概要里的每一条
# 都指向一个章节（`[[#详解]]`，Obsidian 能点），详解删了索引就跟着消失——
# 用生成代替手写，漂移就没有发生的余地。

AUTO_SCORE_BEGIN = "<!-- auto:score:start -->"
AUTO_SCORE_END = "<!-- auto:score:end -->"
AUTO_EXP_BEGIN = "<!-- auto:exp:start -->"
AUTO_EXP_END = "<!-- auto:exp:end -->"

# 章节顺序固定：概要在前，更新记录在最后
SECTION_ORDER = ["概要", "详解", "易错点", "经验与判断",
                 "我的掌握", "我的经历", "关联", "更新记录"]

# 有内容才出现的章节（空着就不写，避免整页都是「待补」）
CONTENT_SECTIONS = [("详解", "它是什么、怎么运转"),
                    ("易错点", "容易错的地方、易混淆的近邻"),
                    ("经验与判断", "我的结论、习惯、判定边界")]

EV_LABEL = {
    "project_lead": "主导项目", "teaching": "讲给别人", "artifact": "有产出",
    "selftest_pass": "通过自测", "study": "系统学习", "self_report": "自评",
    "inferred": "背景推断", "web_inferred": "联网推断",
    "user_confirmed": "本人确认", "forgot": "遗忘", "selftest_fail": "自测未过",
    "rusty_asked": "问了个生疏的", "edge_confirm": "连边确认",
    "verify": "复核", "review": "复盘",
}


def load_evidence(udir, ev_id):
    """读一条证据，返回 meta 或 None。证据只增不改，读失败按缺失处理。"""
    path = os.path.join(udir, "evidence", f"{ev_id}.md")
    if not os.path.exists(path):
        return None
    meta, _ = read_md(path)
    return meta or None


def load_evidence_list(udir, ev_ids):
    """按 id 列表取证据，**按时间倒序**（最近的经历排前面）。"""
    out = []
    for eid in ev_ids or []:
        m = load_evidence(udir, str(eid))
        if m:
            out.append(m)
    out.sort(key=lambda m: str(m.get("occurred_at") or ""), reverse=True)
    return out


def split_body(body):
    """把正文切成 (头部, [(章节名, 内容), ...])。只认 `## ` 二级标题。"""
    lines = (body or "").splitlines()
    idxs = [i for i, l in enumerate(lines) if l.startswith("## ")]
    if not idxs:
        return (body or "").rstrip("\n"), []
    head = "\n".join(lines[:idxs[0]]).rstrip("\n")
    secs = []
    for k, i in enumerate(idxs):
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        secs.append((lines[i][3:].strip(), "\n".join(lines[i + 1:end]).strip("\n")))
    return head, secs


def join_body(head, secs):
    """按 SECTION_ORDER 重排后拼回正文：章节顺序稳定，diff 才读得懂。"""
    order = {t: i for i, t in enumerate(SECTION_ORDER)}
    secs = sorted(secs, key=lambda x: (order.get(x[0], len(SECTION_ORDER)), x[0]))
    out = ([head, ""] if head.strip() else [])
    for t, txt in secs:
        out.append(f"## {t}")
        out.append("")
        if txt.strip():
            out.append(txt.rstrip())
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def get_section(body, title):
    _head, secs = split_body(body)
    for t, txt in secs:
        if t == title:
            return txt
    return ""


def set_section(body, title, text):
    """写入或替换一个章节，其余章节原样保留。空字符串 = 删除该章节。"""
    head, secs = split_body(body)
    text = (text or "").strip("\n")
    found = False
    out = []
    for t, txt in secs:
        if t == title:
            found = True
            if text:
                out.append((t, text))
        else:
            out.append((t, txt))
    if not found and text:
        out.append((title, text))
    return join_body(head, out)


def _days_since(date_str):
    try:
        d = datetime.date.fromisoformat(str(date_str)[:10])
    except (ValueError, TypeError):
        return None
    return (TODAY - d).days


def render_score_block(meta, evs=None):
    """「我的掌握」的自动块：分数、上次接触、证据构成。"""
    raw = float(meta.get("raw_score", 0) or 0)
    cur = float(meta.get("current_score", raw) or 0)
    peak = float(meta.get("peak_score", raw) or 0)
    evs = evs or []
    L = []
    if raw <= 0:
        L.append("- 还没有证据。**0 分不代表「不会」，只代表「没记过」。**")
    else:
        _status, base = judge_status(raw, cur, peak)
        label = LEVEL_LABEL.get(base, base)
        L.append(f"- 分数：累计 **{raw:.0f}** ／ 当前 **{cur:.0f}**（{label}）／ 峰值 {peak:.0f}")
        last = str(meta.get("last_verified_at") or "").strip()
        days = _days_since(last) if last else None
        if last:
            if days == 0:
                L.append(f"- 上次接触：{last}（今天）")
            else:
                L.append(f"- 上次接触：{last}"
                         + (f"（{days} 天前）" if days is not None else ""))
        else:
            L.append("- 上次接触：尚无记录（分数来自冷启动推断）")
    if evs:
        pos = [e for e in evs if str(e.get("direction") or "positive") != "negative"]
        neg = [e for e in evs if str(e.get("direction")) == "negative"]
        parts = []
        for e in pos:
            parts.append(f"{EV_LABEL.get(str(e.get('type')), str(e.get('type')))} "
                         f"{float(e.get('weight', 0) or 0):.0f}")
        if parts:
            L.append(f"- 证据 {len(pos)} 条：" + " · ".join(parts))
        for e in neg:
            L.append(f"- 负向 {EV_LABEL.get(str(e.get('type')), str(e.get('type')))}"
                     f"（{e.get('occurred_at')}）")
    pre = [str(x) for x in (meta.get("prerequisite") or [])]
    if pre:
        L.append("- 前置：" + "、".join(pre))
    return "\n".join(L)


def render_exp_block(evs):
    """「我的经历」的自动块：从证据倒出一条时间线。

    刻意只搬证据里已有的字段（日期 / 类型 / 权重 / 备注），
    不替用户润色——经历必须是发生过的事，不是写出来的故事。
    **种子证据不算经历**：那是「系统猜的」，不是「你干过的」。
    """
    real = [e for e in evs if not is_seed(e)]
    if not real:
        tail = "（当前分数来自背景推断，还没被确认）" if evs else ""
        return ("- 还没有实践记录。**讲过一次、做过一次、踩过一次坑**，"
                f"记一条证据，这里就会自动长出来。{tail}")
    L = []
    for e in real:
        d = str(e.get("occurred_at") or "")[:10] or "（无日期）"
        kind = EV_LABEL.get(str(e.get("type")), str(e.get("type")))
        w = float(e.get("weight", 0) or 0)
        role = "（推断）" if is_seed(e) else ""
        note = str(e.get("note") or "").strip()
        src = str(e.get("source_ref") or "").strip()
        line = f"- {d} · {kind}{role} {w:.0f} 分"
        if note:
            line += f" · {note}"
        if src and not src.startswith("http"):
            line += f"（来源：{src}）"
        elif src:
            line += f"（[来源]({src})）"
        L.append(line)
    return "\n".join(L)


def render_overview(summary, body):
    """生成「概要」：一句话题眼 + 指向实际存在章节的索引。

    索引是**按当前正文算出来的**，不是写死的清单——所以章节删了，
    索引条目自动消失，不会指到不存在的地方。
    """
    _head, secs = split_body(body)
    have = {t for t, txt in secs if txt.strip()}
    L = [f"> 一句话：{summary.strip()}" if (summary or "").strip()
         else "> 一句话：待补（第一次讲解时补上，一句话能说清它是什么）。", ""]
    for title, desc in CONTENT_SECTIONS:
        if title in have:
            L.append(f"- [[#{title}]] — {desc}")
    if "我的掌握" in have:
        L.append("- [[#我的掌握]] — 分数、上次接触、证据构成")
    if "我的经历" in have:
        L.append("- [[#我的经历]] — 哪次实践用到了它")
    if "关联" in have:
        L.append("- [[#关联]] — 相邻知识点、易混淆项")
    return "\n".join(L)


def refresh_body(udir, meta, body, summary=None):
    """重算自动块与概要索引，返回新正文（不落盘）。

    `summary` 为 None 时沿用概要里已有的「一句话」，不会把用户写的题眼冲掉。
    """
    ev_ids = meta.get("evidence_ids") or []
    if isinstance(ev_ids, str):
        ev_ids = [ev_ids] if ev_ids else []
    evs = load_evidence_list(udir, ev_ids)

    body = set_section(body, "我的掌握",
                       f"{AUTO_SCORE_BEGIN}\n{render_score_block(meta, evs)}\n{AUTO_SCORE_END}")
    body = set_section(body, "我的经历",
                       f"{AUTO_EXP_BEGIN}\n{render_exp_block(evs)}\n{AUTO_EXP_END}")

    if summary is None:
        cur = get_section(body, "概要")
        m = re.search(r"^>\s*一句话[：:]\s*(.+)$", cur, re.M)
        summary = m.group(1).strip() if m else ""
        if summary.startswith("待补"):
            summary = ""
    body = set_section(body, "概要", render_overview(summary, body))
    return body


def build_point_body(name, summary="", detail="", pitfalls="", lessons="",
                     meta=None, udir=None, related_block=None, log_lines=None):
    """从零搭一页知识点正文。既有内容没有的情况才用它（迁移 / 新建）。"""
    body = f"# {name}\n"
    for title, text in (("详解", detail), ("易错点", pitfalls),
                        ("经验与判断", lessons)):
        if (text or "").strip():
            body = set_section(body, title, text)
    if related_block is not None:
        body = set_section(body, "关联", related_block)
    logs = list(log_lines or [])
    if logs:
        body = set_section(body, "更新记录", "\n".join(f"- {x}" for x in logs))
    if meta is not None and udir:
        body = refresh_body(udir, meta, body, summary=summary)
    else:
        body = set_section(body, "概要", render_overview(summary, body))
    return body


def add_log(body, text):
    """往「更新记录」追加一行（同一天的重复行只留一条）。"""
    cur = get_section(body, "更新记录")
    line = f"- {text}"
    lines = [l for l in cur.splitlines() if l.strip()]
    if line in lines:
        return body
    lines.append(line)
    return set_section(body, "更新记录", "\n".join(lines))
