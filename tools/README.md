# tools/

## refs-doctor.py

修复本仓库 `.git/refs/remotes/` 松散引用层丢失的工具。

### 症状

`git status` 显示分支 upstream 为 `[gone]`，但 `git show-ref` 又能读到引用。

### 用法

```bash
git refs-fix              # 手动修复（幂等，任何时候可跑）
git refs-fix --check      # 只检查，有问题退出码 1

git fetch-checkout --all  # fetch + 自动修复
git pushfix origin-ssh main   # push + 自动修复
git pullfix               # pull + 自动修复
```

> ⚠️ **裸用 `git fetch` / `git push` 仍会破坏引用层。**
> Git 没有 `post-fetch` 钩子，只能用 alias 包装。

### 安装到新克隆

```bash
cp tools/refs-doctor.py .git/hooks/
PY="$(command -v python3 || command -v python)"
git config alias.refs-fix       "!$PY .git/hooks/refs-doctor.py"
git config alias.fetch-checkout "!git fetch \"\$@\" && $PY .git/hooks/refs-doctor.py >/dev/null 2>&1 || true"
git config alias.pushfix        "!git push \"\$@\" && $PY .git/hooks/refs-doctor.py >/dev/null 2>&1 || true"
git config alias.pullfix        "!git pull \"\$@\" && $PY .git/hooks/refs-doctor.py >/dev/null 2>&1 || true"
```

### 原理

以 **reflog** 为权威值来源（reflog 写盘从未失败），重建
`refs/remotes/*` 与 `refs/heads/*` 的松散文件，并把最新值回写 `packed-refs`。

详细排查过程见 [`../docs/git引用层丢失-排查与修复.md`](../docs/git引用层丢失-排查与修复.md)。
