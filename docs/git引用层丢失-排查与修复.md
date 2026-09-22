# `.git` 引用层异常：排查与修复

> 状态：**已定位根因并验证**（2026-09-23）
> 影响范围：仅本地仓库的引用显示，不影响任何提交内容、历史或远端数据
> 工具：`tools/refs-doctor.py`

## 一、现象

`git status` 长期显示分支的 upstream 消失：

```
$ git branch -vv
* main  157c5a8 [origin-ssh/main: gone] chore: 版本号改为单一来源...
  slim  1c02e6e [origin-ssh/slim: gone] ...
```

推送本身是成功的（远端能拿到正确 SHA），但本地引用显示一直是 `[gone]`。

## 二、自相矛盾的症状（关键线索）

排查中发现同一份数据的读取结果**互相矛盾**：

| 命令 | 结果 |
| ------ | ------ |
| `git show-ref refs/remotes/origin-ssh/main` | ✅ 返回 `cb7ad29` |
| `git for-each-ref`（无参数，全量） | ✅ 列出 33 条，**含** `origin-ssh/main` |
| `git for-each-ref refs/remotes` | ✅ 17 条（含 origin-ssh 的 5 条） |
| `git for-each-ref refs/remotes/origin-ssh` | ❌ **0 条** |
| `git rev-parse --verify refs/remotes/origin-ssh/main` | ❌ `fatal: Needed a single revision` |
| `git rev-parse origin-ssh/main` | ❌ 同样 fatal |
| `git status -sb` | ❌ `[gone]` |

注意第 3、4 行：**父级能列出子级的全部条目，子级自己却返回空**。
这是整条线索的突破口。

## 三、根因：ref 迭代器的「目录级短路」

### 双层存储

Git 的引用数据库有两层：

```
松散层   .git/refs/remotes/origin-ssh/main     （一个文件，内容 = sha）
打包层   .git/packed-refs                      （文本，行 = "<sha> <refname>"）
```

### 短路机制

**遍历引用时，「目录发现」只看文件系统**；`packed-refs` 里的条目
**不会产生对应的虚拟目录**。

所以当 `refs/remotes/origin-ssh/` 下**一个松散文件都没有**时：

```
refs/remotes              → 17 条   ← 父级扫到目录 origin/pr/upstream，
                                       并在这层把 packed 里 origin-ssh 的
                                       条目也一并吐出
refs/remotes/origin-ssh   →  0 条   ← 子级要递归进 origin-ssh 目录，
                                       但该目录不存在 → 整棵子树被跳过
rev-parse origin-ssh/main → fatal
status                    → [gone]
```

### 更隐蔽的第二层：短路是「目录粒度」的

只要该目录下**存在任意一个**松散文件，迭代器就**只迭代松散层**，
`packed-refs` 中同目录的其他条目**继续不可见**：

```bash
# 写入仅 1 个松散文件 origin-ssh/main
$ git for-each-ref refs/remotes/origin-ssh
refs/remotes/origin-ssh/main          # 只有 1 条
# slim / test / toorigin / win 仍在 packed-refs 里，但被吞掉
```

### 为什么只有本仓库中招

四个远端目录的松散层与 packed 层**恰好完全同构**，从未触发短路：

| 目录 | 松散文件 | packed 条目 | 前缀遍历 | 状态 |
| ------ | ------ | ------ | ------ | ------ |
| `origin` | 5 | 5 | 5 | ✅ 同构 |
| `upstream` | 3 | 3 | 3 | ✅ 同构 |
| `pr` | 4 | 4 | 4 | ✅ 同构 |
| `origin-ssh` | **0** | 5 | **0** | ❌ **短路** |

只有 `origin-ssh` 的松散文件会被 fetch 清空，松散数 `0 ≠ 5`，短路才显形。

### 触发条件

`git fetch` 完成后，`.git/refs/remotes/` 下的松散文件被清空且**不重建**。

`GIT_TRACE` 显示 fetch 后会触发 `git maintenance run --auto --no-quiet --detach`；
`GIT_TRACE_REFS` 显示 fetch 期间**没有任何 write/commit 引用事务记录** ——
Git 判定「值未变化 → 无需写引用事务」，但同时又做了清理。

## 四、修正记录：`packed-refs` 排序陷阱

排查中曾踩到一个独立的坑，已修正，记录备查。

`packed-refs` 头行声明 `sorted` 后，Git 会用**二分查找**定位引用。
若实际内容未按 Git 规则排序，整段会被**静默忽略**。

Git 的 refname 排序是**路径感知**的（按 `/` 切段，逐段比较），
与 Python 的码点排序**不同**：

| | `refs/remotes/origin/main` vs `refs/remotes/origin-ssh/main` |
| ------ | ------ |
| Python 码点排序 | `origin-ssh` 在前（`-` = 0x2D < `/` = 0x2F） |
| **Git 路径排序** | `origin/main` 在前（先比 `origin` 段） |

第一版脚本用了 Python 的 `sorted()`，导致头部声明 `sorted` 但内容未排序
→ Git 忽略整段 → 问题以另一种形式复现。

正确写法：

```python
ordered = sorted(refs.items(), key=lambda kv: kv[0].split("/"))
```

> 该陷阱与本次根因**无关**，是独立问题。当前 `packed-refs` 的排序已验证正确
> （`sorted(refs, key=lambda r: r.split('/'))` 与文件实际顺序一致）。

## 五、修复方案

### 核心不变量

**唯一可靠的权威来源是 reflog**（`.git/logs/`）。松散层与 `packed-refs`
都是**不可靠的缓存**：

| 层 | 可靠性 | 表现 |
| ------ | ------ | ------ |
| reflog (`.git/logs/`) | ✅ **权威** | 写盘从未失败，push/fetch 后立即反映最新值 |
| 松散层 (`.git/refs/`) | ⚠️ 会被 fetch 清空 | 清空后触发目录级短路 |
| `packed-refs` | ⚠️ 会**滞后** | push 后仍停留在旧值，不随 push 更新 |

实测（2026-09-23，push `cb7ad29..04fce6b` 之后）：

```
HEAD:              04fce6b   ✅
松散 origin-ssh:   04fce6b   ✅
reflog:            04fce6b   ✅
远端:              04fce6b   ✅
packed origin-ssh: cb7ad29   ❌ 滞后一个提交
```

> 先前"`packed-refs` 始终准确"的结论是**误判**——当时恰好对同一 commit
> 反复操作，掩盖了滞后。以 reflog 为准才是正确做法。

因此修复**不回写 `packed-refs`**（避免在滞后值上做无谓写入），
只把松散层补齐到与**reflog** 一致。

### 权威值来源（优先级）

1. `.git/logs/refs/<refname>` 的**最后一行第 2 个字段**（new-sha）——
   reflog 写盘从未失败，且能反映最新 push
2. `packed-refs`（reflog 缺失时兜底）

### 工具

`tools/refs-doctor.py`（副本 `.git/hooks/refs-doctor.py`，
另备份于 `D:\Dev\ClassAssistant-git-doctor\`）

```bash
python tools/refs-doctor.py            # 修复
python tools/refs-doctor.py --check    # 只检查（有问题退出码 1）
```

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
>
> 每次 fetch 后必须跑一次修复，否则 `rev-parse` / `status` 立即失效
> （已实测：连续 3 轮裸 fetch 后逐轮复现）。

## 六、验证结果

| 项目 | 结果 |
| ------ | ------ |
| 破坏测试（`rm -rf .git/refs/remotes/origin-ssh`） | 检出「缺失 5 条」✅ |
| 一键恢复（`git refs-fix`） | 重建 5 条，`rev-parse` 立即恢复 ✅ |
| `git refs-fix --check` | `正常：22 条松散引用与 reflog / packed-refs 一致` ✅ |
| 连续 3 轮裸 fetch | 逐轮复现 `[gone]`（**证实必须包装**）✅ |
| `git fetch-checkout` 包装命令 | fetch + 修复一步到位，无 `[gone]` ✅ |
| 四方 SHA 一致 | HEAD = `origin-ssh/main`(松散) = reflog = 远端 = `04fce6b` ✅ |
| `packed-refs` 滞后 | push 后仍为 `cb7ad29`（**证实不可作权威源**）⚠️ |
| 松散层同构 | `origin`(5) · `origin-ssh`(5) · `pr`(4) · `upstream`(3) ✅ |

## 七、未验证 / 已知限制

- **未定位到「为什么 fetch 会清空松散层」的环境层面原因**。已排除：
  `core.*` 配置、`extensions.*`、reftable 后端、hooks、权限、路径冲突、
  杀软拦截、沙箱隔离（解除沙箱后现象依旧）、`.git` 写权限（Python 原生写入正常）、
  Git 版本/构建（**两份独立 Git 都复现**：
  `2.55.0.windows.3` @ `D:/git-sdk-64` 与 `2.55.0.windows.5` @ `D:/Program Files/Git`）。
- `windows.appendatomically` / `core.fscache` / `maintenance.auto` 均已试过，无效（已还原）。
- **修复非根治**，是「每次操作后自动重建」的补偿方案。
- `git push` 时对**其他 remote**（如 `origin/*`）的更新也会触发
  `cannot lock ref` 报错，但由 `refs-doctor.py` 在之后修复，不影响推送结果。
- alias 里硬编码了 Python 绝对路径
  （`C:/Users/Infel/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe`），
  换机器需重新配置。

## 八、附：修复前的规避手段

```bash
# 可靠替代：直接问远端
git ls-remote origin-ssh refs/heads/main
```
