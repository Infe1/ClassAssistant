# `.git` 引用层异常：排查与修复

> 状态：**已修复并验证**（2026-09-23）
> 影响范围：仅本地仓库的引用显示，不影响任何提交内容、历史或远端数据

## 一、现象

`git status` 长期显示分支的 upstream 消失：

```
$ git branch -vv
* main  157c5a8 [origin-ssh/main: gone] chore: 版本号改为单一来源...
  slim  1c02e6e [origin-ssh/slim: gone] ...
```

推送本身是成功的（`git ls-remote` 能拿到正确 SHA），但本地引用显示一直是 `[gone]`。

## 二、自相矛盾的症状（关键线索）

排查中发现同一份数据的读取结果**互相矛盾**：

| 命令 | 结果 |
| ------ | ------ |
| `git show-ref origin-ssh/main` | ✅ 返回 `0020b4e...` |
| `git for-each-ref refs/remotes/` | ✅ 列出全部 5 条 `origin-ssh/*` |
| `git rev-parse origin-ssh/main` | ❌ `fatal: Needed a single revision` |
| `git rev-parse refs/remotes/origin-ssh/main` | ❌ 同样 fatal |
| `git status` | ❌ `[gone]` |

`show-ref` 与 `rev-parse` 读的是同一份 `packed-refs`，结果却不同 ——
说明它们走的是**不同的引用查找路径**。

## 三、根因（两条，互相叠加）

### 根因 A：`rev-parse` 的 DWIM 需要松散引用**目录**存在

`git rev-parse origin-ssh/main` 会做「缩写展开」（DWIM），
它要求 `.git/refs/remotes/origin-ssh/` 这个**目录结构存在**才能解析，
无法只依赖 `packed-refs`。

而 `git show-ref` / `git for-each-ref` 直接遍历引用数据库，
不受此限制 —— 这就是症状矛盾的原因。

**实测证据**：手工 `mkdir -p .git/refs/remotes/origin-ssh` 并写入文件后，
`git rev-parse origin-ssh/main` **立刻恢复正常**，`git status` 也变回
`## main...origin-ssh/main`。

### 根因 B：`fetch` / `push` 会清空松散引用层且不重建，`packed-refs` 也不更新

复现步骤（可稳定重现）：

```bash
# 1. 引用正常
$ git rev-parse --short origin-ssh/main
0020b4e

# 2. 执行 fetch —— 报告了更新
$ git fetch origin-ssh
   e12c0e1..0020b4e  main -> origin-ssh/main

# 3. 引用立刻坏了
$ git rev-parse --short origin-ssh/main
fatal: Needed a single revision
$ git status -sb
## main...origin-ssh/main [gone]

# 4. 松散目录被清空（目录都不存在了）
$ ls .git/refs/remotes/
origin  upstream        # origin-ssh 消失了
```

关键点：**`packed-refs` 里的值也不跟着更新**。
`fetch` 打印了 `e12c0e1..0020b4e`，但 `packed-refs` 里仍是 `e12c0e1`。

**唯一始终正确的来源是 reflog**：

```
$ tail -2 .git/logs/refs/remotes/origin-ssh/main
0020b4e... c2d0626... update by push
0020b4e... c2d0626... fetch origin-ssh: fast-forward
```

reflog 的写盘从未失败过。

### 补充：`packed-refs` 的排序陷阱（排查中踩到的坑）

`packed-refs` 头行声明 `sorted` 后，Git 会用**二分查找**定位引用。
若实际内容未按 Git 的规则排序，整段会被**静默忽略**。

Git 的 refname 排序是**路径感知**的（按 `/` 切段，逐段比较），
与 Python 的码点排序**不同**：

| | `refs/remotes/origin/main` vs `refs/remotes/origin-ssh/main` |
| ------ | ------ |
| Python 码点排序 | `origin-ssh` 在前（`-` = 0x2D < `/` = 0x2F） |
| **Git 路径排序** | `origin/main` 在前（先比 `origin` 段） |

第一版修复脚本用了 Python 的 `sorted()`，导致 `packed-refs` 头部
声明 `sorted` 但内容未排序 → Git 忽略整段 → 问题以另一种形式复现。

正确写法：

```python
ordered = sorted(refs.items(), key=lambda kv: kv[0].split("/"))
```

## 四、修复方案

**以 reflog 为权威来源，重建松散引用层 + 回写 `packed-refs`。**

工具：`.git/hooks/refs-doctor.py`（另备份于 `D:\Dev\ClassAssistant-git-doctor\`）

### 优先级

1. `.git/logs/refs/<refname>` 的**最后一行第 2 个字段**（new-sha）
2. `packed-refs`（reflog 缺失时兜底）

### 配套 alias

| alias | 作用 |
| ------ | ------ |
| `git refs-fix` | 手动修复（幂等，任何时候可跑） |
| `git refs-fix --check` | 只检查，有问题退出码 1 |
| `git fetch-checkout` | `fetch` + 自动修复 |
| `git pushfix` | `push` + 自动修复 |
| `git pullfix` | `pull` + 自动修复 |

> ⚠️ **直接用 `git fetch` / `git push` 仍会破坏引用层**。
> Git 没有 `post-fetch` 钩子，无法在官方钩子里拦截，
> 因此用 alias 包装是唯一可靠的办法。

## 五、验证结果

| 项目 | 结果 |
| ------ | ------ |
| `git refs-fix --check` | `正常：22 条引用齐全且与 reflog 一致` |
| 三方 SHA 一致 | HEAD = `origin-ssh/main` = 远端 `main` = `0020b4e` |
| 连续 5 轮 `fetch-checkout` | 全部稳定，无 `[gone]` |
| 真实提交 → `pushfix` 全链路 | 成功，`0020b4e..74625a1`，三方一致 |
| 松散层重建 | `origin`(5) · `origin-ssh`(5) · `pr`(4) · `upstream`(3) |

## 六、未验证 / 已知限制

- **未定位到环境层面的根本原因**。已排除：`core.*` 配置、`extensions.*`、
  reftable 后端、hooks、权限、路径冲突、杀软拦截、沙箱隔离
  （解除沙箱后现象依旧）、`.git` 目录写权限（Python 原生写入正常）。
  这是 **Git 自身在特定环境下的行为异常**，无法从仓库侧根治。
- **修复非根治**，是「每次操作后自动重建」的补偿方案。
  直接裸用 `git fetch` / `git push` 仍会触发。
- `git push` 时对**其他 remote**（如 `origin/*`）的更新也会触发
  `cannot lock ref` 报错，但由 `refs-doctor.py` 在之后修复，不影响推送结果。
- alias 里硬编码了 Python 绝对路径
  （`C:/Users/Infel/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe`），
  换机器需要重新配置。

## 七、附：原始症状的规避手段（修复前）

```bash
# 可靠替代：直接问远端
git ls-remote origin-ssh refs/heads/main
```
