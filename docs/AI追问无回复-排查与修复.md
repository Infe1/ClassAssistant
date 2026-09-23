# AI 追问「无回复」排查与修复

> 现象：AI 追问偶尔显示「当前没有可用回答。」或长时间停在「AI 思考中...」。
> 记录日期：2026-09-22

---

## 一、现象与截图

连续两次追问「详细解释格雷码和二进制码的转换」「你来解释」，均返回同一句
`当前没有可用回答。`

关键观察：**这句文案对不同的失败原因完全相同**，所以无法从界面反推原因。

---

## 二、调用链（事实）

```
InlineAIChat.tsx handleAsk
  → api.ts catchupChat / emergencyRescueChat
    → POST /api/catchup_chat | /api/emergency_rescue_chat
      → rescue_router.py
        → LLMService.answer_catchup_question | answer_rescue_question
          → self._chat(...)
```

`当前没有可用回答。` 只在一处产生：

```python
# api-service/services/llm_service.py（修复前 314 / 388 行）
content = (response.choices[0].message.content or "").strip()
return {"answer": content or "当前没有可用回答。"}
```

⇒ **「无回复」= HTTP 200 正常返回，但 `content` 是空串。**
如果是 HTTP 500，前端会走 `catch` 分支显示「课堂追问失败」；如果是网络错误，会显示
`LLM 调用失败: ...`。既然两者都没出现，说明请求成功、只是正文空了。

---

## 三、两条根因

### 根因 A —— 模型真的返回了空气

`content` 为空有三种互不相同的情况，修复前**全部被合并成同一句话，且没有日志**：

| 情况 | 真实原因 | 修复前表现 |
|---|---|---|
| `tool_calls` 非空、`content` 为空 | 模型是 Agent 型，想调工具；而本服务未实现工具执行 | 完全静默 |
| 只有 `reasoning_content`、`content` 为空 | `max_tokens` 被思维链吃光（追问仅 800 token） | 完全静默 |
| 两者都空 | 模型拒答 / `finish_reason=length` | 完全静默 |

**佐证**：同一项目里 `generate_class_summary` 曾出现「只返回思维链、正文为空」的
0 字节总结（见 `llm_service.py` 上方注释），说明该模型确有此行为；追问的
`max_tokens=800` 比总结小得多，更容易触发。

### 根因 B —— 请求被无限期挂起（`fetch` 没有超时）

- 前端用原生 `fetch`，**`fetch` 本身不支持超时**（不会因等待过久而失败）。
- `AsyncOpenAI` 的 SDK 默认超时经实测为 **600 秒**：

  ```python
  # .venv/Lib/site-packages/openai/_constants.py
  DEFAULT_TIMEOUT = httpx.Timeout(timeout=600.0, connect=5.0)
  ```

  且 SDK 默认 `max_retries=2`，最坏情况是 `3 × 600 = 1800 秒`。
- 后端由 `main.py` 以 `uvicorn.run(app, ...)` 启动 —— **单 worker**。

⇒ 一节课内如果某个 LLM 请求变慢，前端会长时间停在「AI 思考中...」，
按钮全程 `disabled`，用户只能重启应用。

**关于「单 worker 是否真的会阻塞」—— 区分事实与推断：**

- **事实**：`uvicorn.run` 未指定 `workers`，是单 worker。
- **事实**：代码里所有 LLM 调用点都直接用 `await`，其中
  `compress_monitoring_progress` 会由 ASR 回调自动触发
  （`TRANSCRIPT_ENABLE_ROLLING_SUMMARY=1` 时每 50 行一次），
  因此**线上确实存在并发 LLM 请求**。
- **未验证**：慢请求是否真的会把事件循环堵到其他请求完全无法调度。
  这取决于 httpx 是否共用同一个连接池。**没有制造并发慢请求实测过，故不下结论。**

无论如何，根因 B 的修复（超时）独立成立：`fetch` 无超时 + SDK 默认 600 秒，
本身就是「界面卡死」的充分条件，与是否阻塞其他请求无关。

---

## 四、修复内容

按「最小改动、可独立回滚」拆分四块。

### 改动 1 —— `api-service/services/llm_service.py`

**（a）收窄超时**

```python
self.client = AsyncOpenAI(
    base_url=self.base_url,
    api_key=self.api_key,
    timeout=resolve_llm_timeout(),   # 默认 60 秒，env LLM_TIMEOUT 可覆盖
    max_retries=0,                   # 自己控制，避免「超时→重试→再超时」放大卡顿
)
```

新增 `resolve_llm_timeout()`，仿照已有的 `resolve_summary_max_tokens()`：
每次调用重读环境变量，带 `[5, 600]` 上下界校验与告警日志。

**（b）新增 `_extract_text(response, tag)`**

统一抽取正文，并在正文为空时**按三种情况分别打 ERROR 日志**（见第三节根因 A 表格）。
调用方由

```python
content = (response.choices[0].message.content or "").strip()
return {"answer": content or "当前没有可用回答。"}
```

改为

```python
content = self._extract_text(response, "answer_catchup_question")
if not content:
    return {"answer": "模型本次没有返回内容（已记录到后端日志）。请再试一次；…"}
return {"answer": content}
```

**（c）追问失败时补 `logger.exception`**

原来这两个调用点的 `except` 只把报错拼进返回文案，**日志里什么都不留**。
现已补上 `logger.exception("[LLM调用失败] <tag>")`，与同文件
`compress_monitoring_progress:531` 的既有写法保持一致。

### 改动 2 —— `app-ui/src/services/api.ts`

- 新增 `fetchWithTimeout()` + `withTimeout()` + `describeFailure()`。
- `DEFAULT_TIMEOUT_MS = 90_000`（比后端 60 秒留余量，避免前端先于后端放弃）。
- `SUMMARY_TIMEOUT_MS = 180_000`（课后总结在长转录 + 思考型模型下确实慢）。
- **24 处** `await fetch(` 全部改为 `await fetchWithTimeout(`。
- 两个追问接口额外 `.catch()` 把 `AbortError` 翻译为可读文案。

### 改动 3 —— `app-ui/src/components/InlineAIChat.tsx`

- 追问失败时**把问题放回输入框**（`setQuestion(input)`），用户可直接重发。
- 错误块新增「重填」按钮，从消息列表里取回最后一条用户提问。
- 错误块改用 `flex-1 break-words`，长超时文案不再溢出。

### 改动 4 —— `api-service/.env.example`

新增 `LLM_TIMEOUT=60` 及说明注释。

---

## 五、验证方式

### 静态（已完成）

```bash
api-service/.venv/Scripts/python.exe -m py_compile api-service/services/llm_service.py
cd app-ui && npx tsc --noEmit
```

### 实机（待用户执行）

| 观察点 | 期望 |
|---|---|
| 后端日志出现 `[LLM空回复]` | 说明触发了根因 A，日志会写明是 tool_calls / 思维链 / 纯空 |
| 后端日志出现 `[LLM调用失败]` | 说明是网络或鉴权问题 |
| 界面出现「请求超时」 | 说明触发了根因 B，90 秒内必定返回 |
| 界面再也不出现「当前没有可用回答」 | 该文案已从代码中移除 |

**排查建议**：复现时优先看后端日志里有没有 `[LLM空回复]` 或 `[LLM调用失败]`。
两条日志分别对应两个根因，能直接定位。

---

## 六、未做的验证（明确标注）

1. **未实测**根因 B 中「单 worker 被慢请求阻塞」这一具体机制（见第三节说明）。
2. **未实测** 90 秒前端超时 / 60 秒后端超时在真实 DeepSeek 网络下的实际表现。
3. **未改动** `.env` 中的 `LLM_MODEL`。当前为 `deepseek-chat`，
   若日志确认是 tool_calls 导致，才需要换模型；**目前无证据**，故不动。

---

## 六之二、⚠️ 本次改动引入的严重缺陷（已于 2.0.4 修复）

**`app-ui/src/services/api.ts` 的 `fetchWithTimeout` 被误写成调用自身**：

```typescript
return await fetchWithTimeout(url, { ...init, signal });   // 应为原生 fetch
```

造成 `RangeError: Maximum call stack size exceeded`，
**全部 24 处后端请求失效，应用整体不可用**。

| 项 | 内容 |
|---|---|
| 引入版本 | **2.0.3**（本次提交 `daac50e`） |
| 修复版本 | **2.0.4** |
| 为何 `npx tsc --noEmit` 未发现 | 自递归调用的类型签名完全匹配，编译器无从报错 |

> **教训**：上面第五节把「`tsc --noEmit` EXIT=0」列为验证手段，
> 但该缺陷恰恰逃过了类型检查。**静态检查通过 ≠ 改动安全**。
> 涉及函数包装/代理时，必须人工确认内部调用的是目标函数而非自身。

详见 [`前端请求栈溢出-排查与修复.md`](./前端请求栈溢出-排查与修复.md)。

---

## 七、回滚

四处改动互相独立，各自可单独回退：

```bash
git checkout -- api-service/services/llm_service.py
git checkout -- app-ui/src/services/api.ts
git checkout -- app-ui/src/components/InlineAIChat.tsx
git checkout -- api-service/.env.example
```

`.env.example` 仅新增键，用户各自的 `.env` 未被触碰。
