#!/usr/bin/env python3
"""核对知识点正文里的外链：先看清单，再决定要不要联网核。

为什么要这个脚本：知识点里的网址是**别人的资产**，改版、删页、换域名都常见。
链接烂掉没人知道，等于引用白写。而「这条链接会不会烂」有一半在写的时候就判得出来
（短链、追踪参数、搜索结果页），另一半得真发请求才知道。

两个模式：

    python3 check_links.py --user u001            # 只扫，不联网，标出可疑地址
    python3 check_links.py --user u001 --check    # 发请求核状态码，看有没有搬走

**只读不写**：不修改任何档案文件。判定标准见 `references/recording.md` §6.8。
"""
import re
import sys
import argparse
import socket
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor

import core

# 短链：解析目标随时可变，等于把「指向哪」交给了第三方
SHORTENERS = {"t.cn", "bit.ly", "dwz.cn", "suo.im", "tinyurl.com",
              "goo.gl", "url.cn", "sourl.cn", "rebrand.ly"}

# 追踪参数：去掉这些参数后的地址才是真地址
TRACK_PARAMS = ("utm_", "spm", "fbclid", "gclid", "yclid",
                "share_", "shareid", "from_source")

# 临时签名：几小时后就 403
SIGN_PARAMS = ("x-amz-signature", "x-amz-credential", "expires",
               "access_token", "signature")

# 搜索结果页：下次打开已经不是同一批结果
SEARCH_HINTS = ("baidu.com/s", "google.com/search", "bing.com/search",
                "duckduckgo.com/?q", "so.com/s", "sogou.com/web")

# 二手来源：可以留，但必须有官方源兜底（改版、删号、搬迁概率高）
BLOG_HINTS = ("csdn.net", "juejin.cn", "cnblogs.com", "zhihu.com",
              "jianshu.com", "segmentfault.com", "medium.com", "51cto.com")

# 脆弱路径：记的是「位置」不是「内容」。这类地址页面一改版就 404，
# 常见于学校/企业 CMS（/info/1911/28272.htm）与带日期目录的文档站（/docs/2026-06/xxx.pdf）
FRAGILE_PATH = (r"/info/\d+/\d+\.s?html?$", r"/docs?/\d{4}-\d{1,2}/",
                r"/blog/\d+", r"/article/details/\d+", r"/p/\d{6,}")

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'`，。；、）】｜]+")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def collect(udir):
    """从知识点正文里抽外链。返回 [(url, [条目名…]), …]，按 url 归并。"""
    found = {}
    n_points = 0
    for path, meta, body in core.index_points(udir)["items"]:
        n_points += 1
        for url in URL_RE.findall(body):
            url = url.rstrip(".,;:")
            found.setdefault(url, [])
            name = str(meta.get("name", ""))
            if name not in found[url]:
                found[url].append(name)
    return found, n_points


def diagnose(url):
    """离线判定。返回 (等级, 说明)，等级 0=可疑 / 1=二手来源 / 2=看着没问题。"""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    q = parse_qs(p.query, keep_blank_values=True)
    low = url.lower()

    if host in SHORTENERS or any(host.endswith("." + s) for s in SHORTENERS):
        return 0, f"短链（{host}），解析目标随时可变"
    for k in q:
        if any(k.lower().startswith(t) for t in TRACK_PARAMS):
            return 0, f"带追踪参数 {k}，去掉参数后的地址才是真地址"
        if k.lower() in SIGN_PARAMS:
            return 0, f"带临时签名 {k}，过几小时就 403"
    if any(h in low for h in SEARCH_HINTS):
        return 0, "搜索结果页，下次打开不是同一批结果"
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") \
            or host.endswith(".local") or host.startswith("192.168.") \
            or host.startswith("10.") or host.startswith("172.16."):
        return 0, "内网地址，别人打开是空的"
    if any(h in host for h in BLOG_HINTS):
        return 1, "二手来源，可留但要补官方一手文档兜底"
    for pat in FRAGILE_PATH:
        if re.search(pat, p.path):
            return 1, "路径带文章 id 或日期目录，改版就会 404；能换官方文档就别用它"
    return 2, ""


def probe(url, timeout=5.0):
    """发请求核状态。返回 (状态, 说明)。优先 HEAD，被拒再退 GET。"""
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, method=method, headers={"User-Agent": UA})
            with urlopen(req, timeout=timeout) as r:
                final = r.geturl()
                code = r.status
            note = "已迁移到 " + final if final.rstrip("/") != url.rstrip("/") else ""
            return code, note
        except HTTPError as e:
            if e.code in (403, 405, 501) and method == "HEAD":
                continue                     # 不少站点拒 HEAD，换 GET 再试
            return e.code, str(e.reason)[:40]
        except socket.timeout:
            return 0, f"超时（>{timeout:.0f}s）"
        except URLError as e:
            return 0, str(e.reason)[:60]
        except Exception as e:               # SSL、连接重置等
            return 0, type(e).__name__ + ": " + str(e)[:40]
    return 0, "未知"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--check", action="store_true", help="真发请求核状态码")
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--jobs", type=int, default=8)
    a = p.parse_args()

    udir = core.user_dir(a.user)
    found, n_points = collect(udir)
    if not found:
        print(f"扫了 {n_points} 条知识点，正文里没有外链。")
        return

    hosts = {(urlparse(u).hostname or "") for u in found}
    bad, blogs, ok = [], [], []
    for url, where in found.items():
        level, why = diagnose(url)
        (bad if level == 0 else blogs if level == 1 else ok).append((url, where, why))

    print(f"扫了 {n_points} 条知识点，找到 {len(found)} 条外链（{len(hosts)} 个域名）")

    if bad:
        print(f"\n可疑 {len(bad)} 条（换个地址，这些迟早打不开）：")
        for url, where, why in bad:
            print(f"  · {url}\n      {why}\n      出现在：{'、'.join(where)}")
    if blogs:
        print(f"\n二手来源 {len(blogs)} 条（可留，但要有官方源兜底）：")
        for url, where, why in blogs:
            print(f"  · {url}\n      出现在：{'、'.join(where)}")

    if not a.check:
        if ok:
            print(f"\n其余 {len(ok)} 条看着没问题 —— 加 --check 发请求确认它还活着。")
        return

    print(f"\n核 {len(found)} 条（超时 {a.timeout:.0f}s，{a.jobs} 并发）…")
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        results = list(pool.map(lambda u: (u, probe(u, a.timeout)), found))
    good = 0
    for url, (code, note) in results:
        if 200 <= code < 400:
            good += 1
            mark = "✓" if not note else "→"
            print(f"  {mark} {code}  {url}" + (f"\n      {note}" if note else ""))
        else:
            print(f"  ✗ {code or '---'}  {url}\n      {note}")
    print(f"\n汇总：正常 {good} ／ 有问题 {len(results) - good}（共 {len(results)} 条）")
    if good < len(results):
        print("有问题的先别删——按「它讲什么」那句话重新搜一个官方地址替上去。")


if __name__ == "__main__":
    main()
