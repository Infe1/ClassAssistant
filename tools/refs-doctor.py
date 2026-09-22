#!/usr/bin/env python3
"""
修复 .git 的松散引用层（refs-doctor）

问题背景
--------
本仓库环境存在一个 Git 行为异常：`git fetch` / `git push` 完成后，
`.git/refs/remotes/` 下的松散引用目录会被清空，且**不再重建**。
后果：

    $ git fetch origin-ssh
       e12c0e1..0020b4e  main -> origin-ssh/main     # 报告更新了
    $ git rev-parse origin-ssh/main
       fatal: Needed a single revision               # 但解析不了
    $ git status -sb
       ## main...origin-ssh/main [gone]              # 显示 branch 消失了

根因
----
`rev-parse` 的 DWIM 缩写解析要求对应路径的**松散引用目录存在**，
无法只靠 `packed-refs` 完成解析。目录被清空后它直接放弃查找，
于是 `[gone]`。而 `git show-ref` / `git for-each-ref` 走另一条路径，
仍能读到 `packed-refs`，所以症状表现得自相矛盾。

同时 `packed-refs` 里的值**也不会随 fetch/push 更新**，只有 reflog 是准的。

权威值来源（优先级）
--------------------
1. `.git/logs/refs/remotes/<remote>/<branch>` 的**最后一行新值**（reflog 一直写盘正常）
2. `packed-refs`（reflog 缺失时兜底）

方案
----
以 reflog 为准，重建 `refs/remotes/*` 与 `refs/heads/*` 的松散文件，
并把最新值回写 `packed-refs`。幂等、无损。

用法
----
    python .git/hooks/refs-doctor.py            # 修复
    python .git/hooks/refs-doctor.py --check    # 只检查（有问题退出码 1）

    git refs-fix        # 同「修复」
    git fetch-checkout  # fetch + 自动修复
    git pushfix         # push  + 自动修复
    git pullfix         # pull  + 自动修复
"""

from __future__ import annotations

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
GIT_DIR = os.path.dirname(_HERE) if os.path.basename(_HERE) == "hooks" \
    else os.path.join(os.getcwd(), ".git")

PACKED = os.path.join(GIT_DIR, "packed-refs")
REFS = os.path.join(GIT_DIR, "refs")
LOGS = os.path.join(GIT_DIR, "logs")


# ---------------------------------------------------------------- packed-refs

def load_packed() -> dict[str, str]:
    """读取 packed-refs → {refname: sha}"""
    if not os.path.isfile(PACKED):
        return {}
    out: dict[str, str] = {}
    with io.open(PACKED, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                out[parts[1].strip()] = parts[0].strip()
    return out


def write_packed(refs: dict[str, str]) -> None:
    """按 Git 的路径语义排序后写回 packed-refs"""
    ordered = sorted(refs.items(), key=lambda kv: kv[0].split("/"))
    buf = "# pack-refs with: peeled fully-peeled sorted\n"
    buf += "".join("%s %s\n" % (sha, ref) for ref, sha in ordered)
    with io.open(PACKED, "w", encoding="utf-8", newline="") as fh:
        fh.write(buf)


# ------------------------------------------------------------------- reflog

def reflog_tip(refname: str) -> str | None:
    """从 reflog 最后一行取出新值（第 2 个字段）。

    reflog 行格式：
        <old-sha> <new-sha> <name> <email> <ts> <tz>\\t<message>
    """
    # refs/remotes/origin-ssh/main → .git/logs/refs/remotes/origin-ssh/main
    # 注意：logs 目录下仍带 "refs/" 前缀，不能剥掉
    path = os.path.join(LOGS, refname.replace("/", os.sep))
    if not os.path.isfile(path):
        return None
    last = None
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                last = line
    if not last:
        return None
    fields = last.split()
    if len(fields) < 2:
        return None
    sha = fields[1]
    if len(sha) != 40 or sha == "0" * 40:
        return None
    return sha


# ---------------------------------------------------------------- core logic

def want_refs() -> dict[str, str]:
    """汇总所有期望的引用及其最新值（reflog 优先于 packed-refs）"""
    packed = load_packed()
    wanted: dict[str, str] = {}

    for ref, sha in packed.items():
        if ref.startswith(("refs/remotes/", "refs/heads/")):
            wanted[ref] = sha
        else:
            wanted[ref] = sha          # tags / stash 原样保留

    # reflog 覆盖（仅对 heads / remotes 有意义）
    for ref in list(wanted):
        if not ref.startswith(("refs/remotes/", "refs/heads/")):
            continue
        tip = reflog_tip(ref)
        if tip:
            wanted[ref] = tip

    # reflog 里有、packed-refs 里没有的引用（新建分支）
    for scope in ("refs/remotes", "refs/heads"):
        base = os.path.join(LOGS, scope.replace("/", os.sep))
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                if fn == "HEAD":
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, LOGS).replace(os.sep, "/")
                ref = "refs/" + rel if not rel.startswith("refs/") else rel
                tip = reflog_tip(ref)
                if tip:
                    wanted[ref] = tip

    return wanted


def ref_path(refname: str) -> str:
    return os.path.join(REFS, refname[len("refs/"):].replace("/", os.sep))


def repair(check_only: bool = False) -> int:
    wanted = want_refs()
    target = {r: s for r, s in wanted.items()
              if r.startswith(("refs/remotes/", "refs/heads/"))}

    missing: list[str] = []
    stale: list[str] = []

    for ref, sha in sorted(target.items()):
        path = ref_path(ref)
        if not os.path.isfile(path):
            missing.append(ref)
        else:
            with io.open(path, encoding="utf-8") as fh:
                if fh.read().strip() != sha:
                    stale.append(ref)

    packed_drift = [r for r, s in target.items()
                    if load_packed().get(r) not in (None, s)]

    if check_only:
        bad = missing or stale or packed_drift
        if bad:
            print("[refs-doctor] 引用层异常：缺失 %d / 过期 %d / packed 漂移 %d"
                  % (len(missing), len(stale), len(packed_drift)))
            for r in missing:
                print("  缺失  %s" % r)
            for r in stale:
                print("  过期  %s" % r)
            for r in packed_drift:
                print("  漂移  %s" % r)
            return 1
        print("[refs-doctor] 正常：%d 条引用齐全且与 reflog 一致" % len(target))
        return 0

    fixed = 0
    for ref in set(missing) | set(stale):
        path = ref_path(ref)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(wanted[ref] + "\n")
        fixed += 1

    if packed_drift:
        merged = load_packed()
        for ref in packed_drift:
            merged[ref] = wanted[ref]
        write_packed(merged)

    if fixed or packed_drift:
        print("[refs-doctor] 已修复：重建松散 %d 条，回写 packed %d 条"
              % (fixed, len(packed_drift)))
    return 0


if __name__ == "__main__":
    sys.exit(repair(check_only="--check" in sys.argv))
