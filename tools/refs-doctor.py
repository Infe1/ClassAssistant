#!/usr/bin/env python3
"""
修复 .git 的松散引用层（refs-doctor）

症状
----
`git fetch` 之后，远端分支"看起来丢了"：

    $ git fetch origin-ssh
       e12c0e1..0020b4e  main -> origin-ssh/main     # 报告更新了
    $ git rev-parse origin-ssh/main
       fatal: Needed a single revision               # 但解析不了
    $ git status -sb
       ## main...origin-ssh/main [gone]              # 显示 branch 消失了

根因：ref 迭代器的「目录级短路」
--------------------------------
Git 的引用数据库有两层存储：

    松散层  .git/refs/remotes/origin-ssh/main      （文件）
    打包层  .git/packed-refs                       （文本，行 = "<sha> <refname>"）

关键在于：**遍历引用时，目录发现只看文件系统**，`packed-refs` 里的条目
不会产生对应的"虚拟目录"。

于是当 `refs/remotes/origin-ssh/` 下**一个松散文件都没有**时：

    refs/remotes              → 17 条   （父级能列出全部，含 origin-ssh 的 5 条）
    refs/remotes/origin-ssh   →  0 条   （子级整棵子树被跳过）
    rev-parse origin-ssh/main → fatal

更隐蔽的是：只要该目录下**存在任意一个松散文件**，迭代器就**只迭代松散层**，
`packed-refs` 中同目录的其他条目**继续不可见**：

    （写入 origin-ssh/main 松散文件后）
    refs/remotes/origin-ssh   →  1 条   （slim / test / toorigin / win 仍被吞掉）

这解释了症状为何自相矛盾：
`git show-ref <全限定名>` 走精确查找、能读 packed-refs；
`git for-each-ref` 全量遍历走父级、也能列出；
但带 pattern 的遍历与 `rev-parse` / `status` 走目录递归 → 全部失败。

为什么只有本仓库中招
--------------------
本仓库三个远端目录的松散层与 packed 层**恰好完全同构**
（origin 5/5、upstream 3/3、pr 4/4），从未触发短路；
只有 `origin-ssh` 的松散文件会被 fetch 清空，松散数 0 ≠ packed 数 5，
短路才显形。

触发条件
--------
`git fetch` 完成后，`.git/refs/remotes/` 下的松散文件被清空且**不重建**
（fetch 判定"值未变化 → 无需写引用事务"，但它显然做了清理）。

不变量
------
唯一可靠的是 **reflog**（`.git/logs/refs/...`），它写盘从未失败且能反映
最新 push。另外两层都是不可靠的缓存：

    松散层    ⚠️ 会被 fetch 清空（本工具要修的就是它）
    packed-refs ⚠️ 会滞后 —— push 之后仍停留在旧值

实测：push cb7ad29..04fce6b 后，松散 / reflog / 远端均为 04fce6b，
而 packed-refs 里还是 cb7ad29。

因此本工具**不回写 packed-refs**（在滞后的值上写入没有意义），
只把松散层补齐到与 reflog 一致。

权威值来源（优先级）
--------------------
1. `.git/logs/refs/...` reflog 最后一行新值 —— **权威**
2. `packed-refs` —— 仅在 reflog 缺失时兜底

方案
----
遍历 `packed-refs` 中 `refs/remotes/*` 与 `refs/heads/*` 的每一条，
在松散层写出对应文件（值取 reflog 优先）。幂等、无损、不删任何东西。

用法
----
    python tools/refs-doctor.py            # 修复
    python tools/refs-doctor.py --check    # 只检查（有问题退出码 1）

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

# 需要保证"松散层与 packed 层同构"的命名空间
SCOPES = ("refs/remotes/", "refs/heads/")


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


def desired() -> dict[str, str]:
    """松散层应当存在的引用 → 最新值（reflog 优先于 packed-refs）

    注意：packed-refs 只用来提供**引用清单**（哪些 ref 应该有松散文件），
    它给出的值会滞后，必须让 reflog 覆盖。
    """
    wanted = {ref: sha for ref, sha in load_packed().items()
              if ref.startswith(SCOPES)}

    # reflog 覆盖（能反映最新的 push，比 packed-refs 新）
    for ref in list(wanted):
        tip = reflog_tip(ref)
        if tip:
            wanted[ref] = tip

    # reflog 里有、packed-refs 里没有的引用（例如新建但尚未 pack 的分支）
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
                ref = rel if rel.startswith("refs/") else "refs/" + rel
                tip = reflog_tip(ref)
                if tip:
                    wanted[ref] = tip

    return wanted


def ref_path(refname: str) -> str:
    return os.path.join(REFS, refname[len("refs/"):].replace("/", os.sep))


def _survey(wanted: dict[str, str]) -> tuple[list[str], list[str]]:
    """返回 (missing, stale)"""
    missing: list[str] = []
    stale: list[str] = []
    for ref, sha in sorted(wanted.items()):
        path = ref_path(ref)
        if not os.path.isfile(path):
            missing.append(ref)
        else:
            with io.open(path, encoding="utf-8") as fh:
                if fh.read().strip() != sha:
                    stale.append(ref)
    return missing, stale


def repair(check_only: bool = False) -> int:
    wanted = desired()
    missing, stale = _survey(wanted)

    if check_only:
        if missing or stale:
            print("[refs-doctor] 松散引用层不完整：缺失 %d / 过期 %d"
                  % (len(missing), len(stale)))
            for r in missing:
                print("  缺失  %s" % r)
            for r in stale:
                print("  过期  %s" % r)
            print("  修复：git refs-fix")
            return 1
        print("[refs-doctor] 正常：%d 条松散引用与 reflog / packed-refs 一致"
              % len(wanted))
        return 0

    fixed = 0
    for ref in set(missing) | set(stale):
        path = ref_path(ref)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(wanted[ref] + "\n")
        fixed += 1

    if fixed:
        print("[refs-doctor] 已修复：重建松散引用 %d 条" % fixed)
    return 0


if __name__ == "__main__":
    sys.exit(repair(check_only="--check" in sys.argv))
