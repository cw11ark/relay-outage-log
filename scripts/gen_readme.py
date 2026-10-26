#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render README.md from data/content.json (single source of truth).

🔴 `--check` 是**门禁**：渲染结果与磁盘上的 README.md 不一致就非零退出。
   ⇒ 「README 被人手改过」无法静默通过（项目 CLAUDE.md：README ⛔ 不手改）。

⚠️ 本文件对所有新仓**通用** —— 由 content.json 驱动，⛔ 不为单个仓改渲染逻辑。
   要改样式 ⇒ 改这里 + 重跑所有仓的 `--check`（看有没有把老仓改漂移）。

用法：
    python3 scripts/gen_readme.py           # 写出 README.md
    python3 scripts/gen_readme.py --check   # 只校验，不写
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "content.json")
OUT = os.path.join(ROOT, "README.md")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def anchor(s):
    """GitHub 风格的锚点：小写、去标点、空格转连字符。"""
    keep = [c for c in s.lower() if c.isalnum() or c in " -_"]
    return "".join(keep).strip().replace(" ", "-")


def render(d):
    m, secs = d["meta"], d["sections"]
    L = []
    # 🔴 2026-10-17：日期进 **H1**，⛔ 不只放正文末尾。
    #    理由（Darion 指出，jdnei 实证）：Google 摘要抓的是标题那一行；
    #    用户第一眼看到的也是它。「今天刚更新」同时买到**可信度**和**活跃度权重**。
    #    ⚠️ 旧版放在第 72 行 `- Last updated:` —— 爬虫和用户都等于没看见。
    L.append("# %s (updated %s)" % (m["title"], d.get("updated", "")))
    L.append("")
    L.append("> %s" % m["tagline"])
    L.append("")
    L.append(m["intro"])
    L.append("")

    if m.get("disclaimer"):
        L.append("> [!NOTE]")
        L.append("> %s" % m["disclaimer"])
        L.append("")

    # 目录（章节数 ≥3 才加，少的时候是噪音）
    if len(secs) >= 3:
        L.append("## Contents")
        L.append("")
        for s in secs:
            L.append("- [%s %s](#%s)" % (s.get("icon", ""), s["title"],
                                         anchor(s["title"])))
        L.append("")

    for s in secs:
        icon = (s.get("icon", "") + " ").lstrip()
        L.append("## %s%s" % (icon, s["title"]))
        L.append("")
        if s.get("description"):
            L.append(s["description"])
            L.append("")
        rows = []
        for it in s["items"]:
            name = "[%s](%s)" % (it["name"], it["url"])
            tags = ", ".join("`%s`" % t for t in it.get("tags", []))
            rows.append([name, it["what"], tags] if tags else [name, it["what"]])
        heads = ["Project", "What it is", "Tags"] if any(
            it.get("tags") for it in s["items"]) else ["Project", "What it is"]
        L.append(table(heads, rows))
        L.append("")

    n = sum(len(s["items"]) for s in secs)
    L.append("---")
    L.append("")
    L.append("## About this list")
    L.append("")
    L.append("- **%d** entries across **%d** sections." % (n, len(secs)))
    L.append("- Compiled from public sources; every linked project carries its own license.")
    L.append("- Last updated: **%s**." % d["updated"])
    L.append("- Data lives in `data/content.json` — this README is generated, do not edit by hand.")
    L.append("")
    L.append("## License")
    L.append("")
    L.append("The text and curation in this repository are licensed under "
             "CC BY 4.0. Linked projects keep their own licenses.")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    want = render(d)
    if a.check:
        have = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if have != want:
            print("🔴 README.md 与 data/content.json **漂移**（改数据后忘了重渲染，"
                  "或 README 被手改）")
            print("   ⇒ 跑 `python3 scripts/gen_readme.py` 重写")
            return 1
        print("✅ README.md 与 data/content.json 一致（%d 字节）" % len(want))
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(want)
    print("✅ 已写出 README.md（%d 字节）" % len(want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
