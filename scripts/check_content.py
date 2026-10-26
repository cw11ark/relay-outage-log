#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P-016-G · 新仓内容门禁 —— **脚手架不可能被误判成"建好了"**。

🔴 为什么需要它：模板里全是 `__PLACEHOLDER__`。若没有这道门禁，
   "复制模板 → 建仓"会在**内容还没写**的情况下走完全流程并报成功
   —— 又是「成功的表象由错误的一侧提供」。

用法：
    python3 scripts/check_content.py            # 校验 data/content.json
    python3 scripts/check_content.py --selftest # 自检（本文件自带，⛔ 不依赖外部）

判据（每条都必须**能失败**，见团队 CLAUDE.md §八·一·1 #1）：
  ① ⛔ 任何 `__XXX__` 占位符残留 ⇒ 失败
  ②  schema：meta / sections / verification_sources 必填且非空
  ③ 🔴 `expected_token` 不得**过短或无区分度** —— 那会让 verify_sources 变成恒真断言
  ④ 🔴 不得有**空章节 / 空条目 / 重复 URL**（重复 = 清单注水）
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = re.compile(r"__[A-Z0-9_]+__")
# 🔴 源 token 的最小长度：太短的 token（如 "a"/"the"）几乎任何页面都能命中 ⇒ 恒真断言
MIN_TOKEN = 6
MIN_ITEMS = 1


def _is_str(v, minlen=1):
    return isinstance(v, str) and len(v.strip()) >= minlen


def fail(msgs, m):
    msgs.append(m)


def check(d):
    """返回错误列表（空 = 通过）。"""
    errs = []

    # ① 占位符
    raw = json.dumps(d, ensure_ascii=False)
    for ph in sorted(set(PLACEHOLDER.findall(raw))):
        fail(errs, "占位符未替换：%s" % ph)

    # ② schema
    if not isinstance(d, dict):
        return ["顶层必须是对象"]
    meta = d.get("meta")
    if not isinstance(meta, dict):
        fail(errs, "缺 meta")
    else:
        for k, mn in (("title", 4), ("tagline", 8), ("intro", 20), ("owner_repo", 3)):
            if not _is_str(meta.get(k), mn):
                fail(errs, "meta.%s 缺失或过短（需 ≥%d 字符）" % (k, mn))
        if _is_str(meta.get("owner_repo")) and "/" not in meta["owner_repo"]:
            fail(errs, "meta.owner_repo 必须是 `owner/name` 形式")
    if not _is_str(d.get("updated")):
        fail(errs, "缺 updated")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", d["updated"]):
        fail(errs, "updated 必须是 YYYY-MM-DD")

    # ③ 章节与条目
    secs = d.get("sections")
    if not isinstance(secs, list) or not secs:
        fail(errs, "sections 必须是非空数组")
        secs = []
    seen, n_items = set(), 0
    for i, s in enumerate(secs):
        tag = "sections[%d]" % i
        if not isinstance(s, dict):
            fail(errs, "%s 必须是对象" % tag); continue
        for k, mn in (("title", 2), ("description", 10)):
            if not _is_str(s.get(k), mn):
                fail(errs, "%s.%s 缺失或过短" % (tag, k))
        items = s.get("items")
        if not isinstance(items, list) or len(items) < MIN_ITEMS:
            fail(errs, "%s.items 必须至少 %d 条（空章节 = 注水）" % (tag, MIN_ITEMS))
            continue
        for j, it in enumerate(items):
            t2 = "%s.items[%d]" % (tag, j)
            if not isinstance(it, dict):
                fail(errs, "%s 必须是对象" % t2); continue
            for k, mn in (("name", 2), ("url", 10), ("what", 15)):
                if not _is_str(it.get(k), mn):
                    fail(errs, "%s.%s 缺失或过短" % (t2, k))
            u = it.get("url")
            if _is_str(u):
                if not u.startswith("http"):
                    fail(errs, "%s.url 必须 http(s) 开头" % t2)
                if u in seen:
                    fail(errs, "%s.url 与前面**重复**（清单注水）：%s" % (t2, u))
                seen.add(u)
            n_items += 1
    if n_items and n_items < 5:
        fail(errs, "全仓条目仅 %d 条 —— 清单仓太少不足以建仓（阈值 5）" % n_items)

    # ④ 取证源（verify_sources.py 的输入）
    srcs = d.get("verification_sources")
    if not isinstance(srcs, list) or not srcs:
        fail(errs, "verification_sources 必须非空（⛔ 空列表是**能在不证明任何事的情况下通过**的门禁）")
        srcs = []
    if srcs and len(srcs) < 5:
        fail(errs, "取证源仅 %d 个 —— 太少，覆盖不足（阈值 5）" % len(srcs))
    sseen = set()
    for i, s in enumerate(srcs):
        t = "verification_sources[%d]" % i
        if not isinstance(s, dict):
            fail(errs, "%s 必须是对象" % t); continue
        for k in ("name", "url", "expected_token"):
            if not _is_str(s.get(k)):
                fail(errs, "%s.%s 必填" % (t, k))
        u = s.get("url")
        if _is_str(u):
            if not u.startswith("http"):
                fail(errs, "%s.url 必须 http(s) 开头" % t)
            if u in sseen:
                fail(errs, "%s.url 重复" % t)
            sseen.add(u)
        # 🔴 恒真断言检查：token 太短 ⇒ 几乎任何页面都能命中
        tok = s.get("expected_token") or ""
        if _is_str(tok) and len(re.sub(r"\s+", "", tok)) < MIN_TOKEN:
            fail(errs, "%s.expected_token 过短（< %d 字符）⇒ 几乎任何页面都命中，"
                       "等于**恒真断言**" % (t, MIN_TOKEN))
    return errs


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def selftest():
    """⭐⭐ 关键：每个判据都要有**能打红它**的反例（否则门禁是装饰）。"""
    import copy
    base = {"updated": "2026-01-01",
            "meta": {"title": "A Good List", "tagline": "A long enough tagline",
                     "intro": "A sufficiently long introduction string here.",
                     "owner_repo": "o/r"},
            "sections": [{"title": "S1", "description": "a long enough description",
                          "items": [{"name": "n%d" % i, "url": "https://e.com/%d" % i,
                                     "what": "x" * 20} for i in range(6)]}],
            "verification_sources": [{"name": "s%d" % i, "url": "https://e.com/s%d" % i,
                                      "expected_token": "tok-%d-long" % i}
                                     for i in range(6)]}
    fails = 0

    def P(ok, label):
        nonlocal fails
        print("  %s  %s" % ("PASS" if ok else "🔴 FAIL", label))
        fails += (not ok)

    P(check(base) == [], "基线（合法内容）通过")
    P("__TITLE__" not in base["meta"]["title"], "基线本身不含占位符（防基线假绿）")

    cases = [
        ("占位符残留被抓", lambda d: d["meta"].__setitem__("title", "__TITLE__")),
        ("空 sections 被抓", lambda d: d.__setitem__("sections", [])),
        ("空 items 被抓", lambda d: d["sections"][0].__setitem__("items", [])),
        ("条目太少被抓", lambda d: d["sections"][0].__setitem__(
            "items", d["sections"][0]["items"][:2])),
        ("重复 URL 被抓", lambda d: d["sections"][0]["items"][1].__setitem__(
            "url", d["sections"][0]["items"][0]["url"])),
        ("缺取证源被抓", lambda d: d.__setitem__("verification_sources", [])),
        ("🔴 恒真 token 被抓", lambda d: d["verification_sources"][0].__setitem__(
            "expected_token", "a")),
        ("坏 owner_repo 被抓", lambda d: d["meta"].__setitem__("owner_repo", "noslash")),
        ("坏日期被抓", lambda d: d.__setitem__("updated", "2026/01/01")),
        ("条目 url 非 http 被抓", lambda d: d["sections"][0]["items"][0].__setitem__(
            "url", "ftp://x")),
    ]
    for label, mut in cases:
        d = copy.deepcopy(base)
        mut(d)
        P(check(d) != [], label)

    print("\n  用例统计：%d 例，失败 %d" % (len(cases) + 1, fails))
    print("✅ 全部通过" if not fails else "🔴 %d 项失败" % fails)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(ROOT, "data", "content.json"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not os.path.exists(a.file):
        sys.exit("🔴 找不到 %s" % a.file)
    errs = check(load(a.file))
    if errs:
        print("🔴 内容门禁**未通过**（%d 项）：" % len(errs))
        for e in errs:
            print("   · " + e)
        return 1
    print("✅ 内容门禁通过：%s" % a.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
