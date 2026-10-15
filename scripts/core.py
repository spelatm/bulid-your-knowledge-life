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
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n" + body)


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
