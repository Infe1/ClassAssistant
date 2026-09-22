# tools/

## refs-doctor.py

修复本仓库 `.git/refs/remotes/` 松散引用层丢失的工具。

### 症状

`git status` 显示分支 upstream 为 `[gone]`，但 `git show-ref` 又能读到引用。

```
git status -sb                          ## main...origin-ssh/main [gone]
git rev-parse origin-ssh/main           fatal: Needed a single revision
git show-ref refs/remotes/origin-ssh/main   ✅ cb7ad29...
git for-each-ref refs/remotes               ✅ 17 条（含 origin-ssh）
git for-each-ref refs/remotes/origin-ssh    ❌ 0 条
```

### 根因

**ref 迭代器的「目录级短路」**：遍历引用时目录发现只看文件系统，
`packed-refs` 里的条目不会产生对应的虚拟目录。

`refs/remotes/origin-ssh/` 下没有任何松散文件时，整棵子树在递归时被跳过
（父级 `refs/remotes` 能列出全部 17 条，子级返回 0 条）。

触发条件是 `git fetch` 完成后清空 `.git/refs/remotes/` 下的松散文件且不重建。
本仓库四个远端目录中，只有 `origin-ssh` 的松散层与 packed 层不同构（0 vs 5），
其余三个恰好完全一致，所以只有它显形。

> **关键不变量**：`packed-refs` 的内容始终准确，fetch / push 都不破坏它。
> 缺的只有松散层文件，所以修复**不需要回写 packed-refs**。

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

按 `packed-refs` 中 `refs/remotes/*` 与 `refs/heads/*` 的每一条，
在松散层写出对应文件（值取 reflog 优先、packed-refs 兜底），
把松散层补齐到与 packed 层**同构**。幂等、无损、不删任何东西。

详细排查过程见 [`../docs/git引用层丢失-排查与修复.md`](../docs/git引用层丢失-排查与修复.md)。
