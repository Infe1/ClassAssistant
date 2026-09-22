# 🦊 课狐 ClassFox - 你的上课摸鱼搭子 🐟

> ClassFox — Hears what you miss.
>
> ClassFox 课狐 —— 听见你的错过，接住你的惊慌。
>
> 以耳廓狐为灵感的小体量 Windows 课堂悬浮助手：资源占用轻，
> 专门盯住你最容易错过的点名、提问和进度变化。

<!-- markdownlint-disable MD033 -->
<div align="center">
  <img src="docs/img/logo透明背景.png" alt="课狐 ClassFox Logo" width="128" />
  <br />
  <a href="https://github.com/Infe1/ClassAssistant/stargazers">
    <img src="https://img.shields.io/github/stars/Infe1/ClassAssistant?style=for-the-badge&logo=github" alt="GitHub stars" />
  </a>
  <a href="https://github.com/Infe1/ClassAssistant/issues">
    <img src="https://img.shields.io/github/issues/Infe1/ClassAssistant?style=for-the-badge&logo=github" alt="GitHub issues" />
  </a>
  <a href="https://github.com/Infe1/ClassAssistant/releases">
    <img src="https://img.shields.io/github/v/release/Infe1/ClassAssistant?style=for-the-badge&logo=github" alt="Latest release" />
  </a>
</div>
<!-- markdownlint-enable MD033 -->

---

## 📌 关于本项目

本仓库是基于上游 [ouyangyipeng/ClassAssistant](https://github.com/ouyangyipeng/ClassAssistant)
**持续维护的分支**，当前版本 **v2.0.3**。

> **本项目与上游的方向已经出现明显区别。**
> 上游以「功能面的横向铺开」为主；本分支的重心转向
> **稳定性、可诊断性和使用链条的收口** ——
> 把「一次都不能出错」的课堂场景当作第一约束，
> 优先修掉那些「偶发、说不清、用户只能干等」的问题。

### 本分支的维护取向

| 取向 | 说明 |
| ------ | ------ |
| 🩺 **可诊断优先** | 出错时日志必须能直接指出原因，禁止把多种失败折叠成同一句兜底文案 |
| ⏱️ **不无限等待** | 所有网络请求都必须有明确超时上限，界面不允许出现永久「思考中」 |
| 🔪 **最小可回滚增量** | 改动尽量拆成互相独立的小块，每块可单独回滚，不做推翻重做 |
| 📚 **文档随码** | 每个修复配一份 `docs/` 记录，含明确标注的未验证项 |

### 相对上游的主要差异

- **AI 追问稳定性**：修复了「偶发无回复」与「长时间卡住」两类问题（见 v2.0.3）。
- **思考型模型适配**：修复长课堂总结写出 0 字节文件的问题，`SUMMARY_MAX_TOKENS` 可配置。
- **请求超时护栏**：后端新增 `LLM_TIMEOUT`，前端全部请求统一加超时。
- **图标清晰度**：补全 `icon.ico` 缺失的 DPI 尺寸（40/48/64px）。
- **文档策略**：不再维护独立 docs 站点，全部文档随仓库走。

---

## 🚀 v2.0.3 近期优化

- **修复 AI 追问偶尔返回「当前没有可用回答」**：该提示实际表示请求已成功返回，
  只是正文为空。此前三种互不相同的空回复原因（模型返回工具调用 / 思维链吃光
  `max_tokens` / 模型拒答）被合并成同一句话，且日志中不留任何记录，
  排查时完全无从下手。现已分别记录，可直接定位。
- **修复追问可能长时间卡在「AI 思考中...」**：`fetch` 无原生超时，叠加 openai SDK
  默认 600 秒超时与 2 次重试，最坏可达 30 分钟，期间界面完全无响应。
  现后端超时收窄至 60 秒，前端 24 处请求统一加入超时，
  超时后把提问自动放回输入框，可直接重发。
- **修复任务栏图标模糊**：`icon.ico` 原本只有 16/32/128/256 四种尺寸，
  缺少 125% / 150% / 200% 显示缩放所需的 40/48/64px，系统只能放大 32px 顶替。
  现补全为 16/24/32/48/64/128/256 七种尺寸，并统一改为 PNG 格式。
- **新增 prompt 缓存命中日志**：日志输出 `[LLM缓存]` 行，用于观察服务端前缀缓存策略效果。
- **调整请求内容顺序**：课程资料前置、转录后置，使公共前缀稳定以命中服务端前缀缓存（语义未变）。

历史版本变更见 [📝 更新说明](#-更新说明)。

## 🎬 Demo

### 摸鱼监控状态

![摸鱼监控状态演示](docs/img/%E6%91%B8%E9%B1%BC%E7%8A%B6%E6%80%81.gif)

### 点名警报与 AI 救场

![点名警报与 AI 救场演示](docs/img/%E7%82%B9%E5%90%8D%E8%AD%A6%E6%8A%A5%E4%B8%8Eai%E5%9B%9E%E7%AD%94.gif)

### 老师讲到哪儿了

![老师讲到哪儿了演示](docs/img/%E8%80%81%E5%B8%88%E8%AE%B2%E5%88%B0%E5%93%AA%E5%84%BF%E4%BA%86.gif)

## ✨ 核心功能

| 功能 | 说明 |
| ------ | ------ |
| 🎙️ 实时语音监控 | 7 种 ASR 模式可切换，从零配置的本地识别到云端高精度识别 |
| 🧹 去重转录 | 流式识别结果按句落盘，过滤重复、碎片标点和相近修正文 |
| 🚦 双级关键词告警 | 红色（点名/提问）与黄色（重点/作业/考试）两档，命中即弹层推送 |
| 🧠 转录保留策略 | 默认完整保留课堂转录，支持按开关启用滚动摘要压缩 |
| 🆘 一键救场 | 结合最近转录和课程资料，生成应答思路与参考答案 |
| 💬 AI 追问对话 | 救场结果与进度总结都支持连续追问，答案可回看 |
| 📍 老师讲到哪了 | 对最近课堂内容做即时进度总结 |
| 📝 课后总结 | 停止监控时自动生成 Markdown 笔记并落盘到 `data/summaries` |
| 📄 资料上传与引用 | PPT / PDF / Word 解析后存入 `data/cite`，开始监控前可选择引用 |
| 🎛️ 提示词预设 | 救场 / 进度 / 两种追问各有内置预设，可切换或存为草稿 |
| ⚙️ 内置设置面板 | 前端直接编辑后端 `.env`，并按分组表单化 |
| 🎨 界面风格自定义 | 4 种背景主题、窗口圆角、透明度、字体缩放可调，设置本地持久化 |

## 🏗️ 架构概览

```text
Tauri 2 + React 19 UI
        │
        ├─ HTTP API   (24 处请求，统一超时护栏)
        └─ WebSocket  /api/ws/alerts
                │
          FastAPI Backend  (uvicorn, 127.0.0.1:8765)
                │
      ┌─────────┼──────────┬─────────────┐
      │         │          │             │
     ASR       LLM    Transcript       PPT
      │         │          │             │
  local / windows     class_transcript.txt   python-pptx
  winasr / webspeech  current_class_material.txt  pypdf
  dashscope / seed    data/cite/*.txt            python-docx
  mock                data/summaries/*.md
```

后端负责录音、ASR、关键词检测、转录落盘和 LLM 调用；
前端负责悬浮窗 UI、警报展示、资料上传、监控启动参数选择和设置编辑。

### 目录结构

```text
ClassAssistant/
├── api-service/                # FastAPI 后端
│   ├── main.py
│   ├── config.py               # 开发态 / 打包态 DATA_DIR 统一
│   ├── backend.spec            # PyInstaller 配置
│   ├── routers/
│   │   ├── monitor_router.py   # 启停 / 转录 / 关键词 / WebSocket
│   │   ├── rescue_router.py    # 救场 / 进度 / 两个追问接口
│   │   ├── summary_router.py   # 课后总结
│   │   ├── ppt_router.py       # 资料上传解析
│   │   ├── prompt_router.py    # 提示词预设
│   │   └── settings_router.py  # .env 读写
│   └── services/
│       ├── asr_service.py      # 7 种 ASR 实现的工厂
│       ├── llm_service.py      # LLM 调用、超时解析、空回复分类
│       ├── monitor_service.py  # 录音循环 + 关键词判定
│       ├── transcript_service.py
│       ├── summary_service.py
│       ├── prompt_service.py
│       └── ppt_service.py
├── app-ui/                     # Tauri + React 前端
│   ├── src/
│   │   ├── App.tsx             # 面板显隐与窗口尺寸统一管理
│   │   ├── components/
│   │   │   ├── TitleBar.tsx        # 无边框自定义拖拽标题栏
│   │   │   ├── ToolBar.tsx         # 主操作栏
│   │   │   ├── StartMonitorPanel.tsx
│   │   │   ├── TranscriptViewer.tsx
│   │   │   ├── InlineAIChat.tsx    # AI 追问（在用）
│   │   │   ├── AlertOverlay.tsx    # 红/黄警报弹层
│   │   │   ├── SettingsPanel.tsx
│   │   │   ├── MarkdownRenderer.tsx
│   │   │   └── Toast.tsx
│   │   └── services/
│   │       ├── api.ts              # 全部 HTTP 调用 + 超时封装
│   │       └── preferences.ts      # UI 风格设置持久化
│   └── src-tauri/                  # Rust 壳、托盘、后端拉起与退出清理
├── data/                       # 运行时数据
├── docs/                       # 文档（含各版本排查记录）
├── winasr/                     # C# WinRT ASR 桥接控制台
├── dev.bat                     # 一键开发启动
└── build.ps1                   # 一键打包
```

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Infe1/ClassAssistant.git
cd ClassAssistant
```

> 如需跟进上游改动，可自行添加 upstream：
> `git remote add upstream https://github.com/ouyangyipeng/ClassAssistant.git`

### 2. 配置后端 Python 环境

项目固定使用 `api-service/.venv`，调试、验证和打包都从这个环境出发。

```bash
cd api-service
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pyinstaller
```

### 3. 配置前端依赖

```bash
cd app-ui
npm install
```

打包前端还需要本机安装 Rust 与 Visual Studio Build Tools，并启用
「使用 C++ 的桌面开发」工作负载。

### 4. 配置环境变量

在 `api-service` 下创建 `.env`，可参考 `.env.example`：

```env
# ---- 服务 ----
API_PORT=8765

# ---- LLM（OpenAI 兼容接口）----
LLM_BASE_URL=https://api.deepseek.com/
LLM_API_KEY=sk-your-api-key
LLM_MODEL=deepseek-chat
# 课后总结的 max_tokens（默认 20000，范围 2000-64000）
# 思考型模型会先输出思维链，额度不足时正文会被挤成空串（表现为 0 字节笔记）
SUMMARY_MAX_TOKENS=20000
# 单次 LLM 请求超时（秒，默认 60，范围 5-600）
LLM_TIMEOUT=60

# ---- ASR ----
# local | windows | winasr | webspeech | dashscope | seed-asr | mock
ASR_MODE=local
WEBSPEECH_LANG=zh-CN

# ---- 转录策略 ----
# 0=完整保留（默认）, 1=每 50 行滚动压缩为历史摘要
TRANSCRIPT_ENABLE_ROLLING_SUMMARY=0

# ---- 云端 ASR 凭据 ----
DASHSCOPE_API_KEY=sk-your-dashscope-key
DASHSCOPE_ASR_MODEL=fun-asr-realtime
SEED_ASR_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
SEED_ASR_APP_KEY=
SEED_ASR_ACCESS_KEY=
SEED_ASR_RESOURCE_ID=volc.bigasr.sauc.duration

# ---- 录音参数 ----
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_CHUNK_SIZE=1024
```

### 5. 启动开发模式

推荐直接运行根目录的 `dev.bat`。它会先清理残留状态，再依次拉起后端与前端：

- 上一次残留的 `class-assistant-backend.exe`
- 标题为 `ClassAssistant-Backend` 的开发后端终端
- 占用 8765 端口的旧进程

也可以手动分别启动：

```bash
cd api-service
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

```bash
cd app-ui
npm run tauri dev
```

## 🧭 使用流程

1. 点击「上传资料」，把 PPT / PDF / Word 解析为可引用文本。
2. 点击「开始摸鱼」，在启动面板里填写课程名称，并可选择一份资料。
3. 后端开始监听课堂音频，按句落盘到 `data/class_transcript.txt`。
4. 命中关键词时，前端立即弹出红色或黄色警报层。
5. 需要时点击「救场」或「老师讲到哪了」，并可继续追问。
6. 点击「停止」结束监控，后端自动生成 Markdown 笔记。

## 🎙️ ASR 模式说明

由 `services/asr_service.py` 的工厂函数按 `ASR_MODE` 分发，共 **7 种**：

| 模式 | 实现 | 说明 |
| ------ | ------ | ------ |
| `local` | `LocalASR` | SpeechRecognition + Google Speech API，按句回调，**无需密钥、开箱可用**（需联网） |
| `windows` | `WindowsBuiltInASR` | Windows 内置识别（WinRT `SpeechRecognizer`），直接调用本机能力 |
| `winasr` | `WinAsrBridgeASR` | 通过 `winasr/WinAsr.exe`（C# + WinRT 控制台）桥接，可调静音/置信度阈值 |
| `webspeech` | `BrowserSpeechASR` | 前端 Web Speech API 识别后回传，别名 `edge-webspeech`、`browser` |
| `dashscope` | `DashScopeASR` | 阿里云百炼 Fun-ASR，模型名可用 `DASHSCOPE_ASR_MODEL` 或启动参数覆盖 |
| `seed-asr` | `SeedASR` | 字节 Seed-ASR，使用 utterances + `definite` 分句 |
| `mock` | `MockASR` | 不录音、不识别，适合纯 UI 联调 |

> 设置面板里 `windows` 与 `winasr` 会统一归一为 `winasr`（见 `monitor_router`），
> 其余任何未匹配的值都落到 `MockASR`。

### 当前转录策略

- `local` / `windows` / `winasr` 保持「识别完一句追加一行」的本地模式。
- `seed-asr` 只把 `definite` 的稳定句落盘，partial 文本仅保存在内存中。
- 会过滤孤立标点、极短碎片和与近期内容高度相似的重复句。
- 默认完整保留课堂转录，不做滚动压缩，便于回看和阅读。
- 如需减少上下文体积，可将 `TRANSCRIPT_ENABLE_ROLLING_SUMMARY` 设为 `1`，
  每 50 条触发一次滚动摘要，并在转录文件里以 `=== 历史摘要 开始/结束 ===` 分块。

### Local ASR 调优参数

```
energy_threshold      = 220
pause_threshold       = 0.9
phrase_threshold      = 0.35
non_speaking_duration = 0.45
phrase_time_limit     = 15
```

`MonitorService` 另针对本地模式做了短时片段合并：后一段若是前一段的扩展识别结果则覆盖上一条；
前一段很短或未自然收尾、且两段间隔不超过 3 秒时拼接为同一条。该逻辑不影响 Seed-ASR 的分句策略。

## ⏱️ 请求超时策略

课堂场景下「卡住」比「报错」更难受，因此前后端各有一层超时护栏：

| 层 | 位置 | 默认值 | 配置项 |
| ------ | ------ | ------ | ------ |
| 前端通用请求 | `api.ts` → `DEFAULT_TIMEOUT_MS` | 90 秒 | 代码常量 |
| 前端课后总结 | `api.ts` → `SUMMARY_TIMEOUT_MS` | 180 秒 | 代码常量 |
| 后端 LLM 调用 | `llm_service.py` → `resolve_llm_timeout()` | 60 秒 | `.env` 的 `LLM_TIMEOUT`（范围 5-600） |

后端同时把 openai SDK 的 `max_retries` 置为 `0`，避免「超时 + 重试」叠加成数倍等待。
前端超时后会显示明确提示，并把刚才的提问放回输入框，可直接重发。

## 📁 运行时数据

| 路径 | 用途 |
| ------ | ------ |
| `data/class_transcript.txt` | 当前课堂完整记录（默认不压缩；开启开关后含历史摘要块） |
| `data/current_class_material.txt` | 当前选中的参考资料文本 |
| `data/cite/` | 上传资料解析后的候选引用文本 |
| `data/keywords.txt` | 红色告警关键词（点名/提问类），`#` 开头为注释 |
| `data/attention_keywords.txt` | 黄色提醒关键词（重点/作业/考试类） |
| `data/prompts.json` | 提示词预设、当前选择与自定义草稿 |
| `data/summaries/` | 生成的课堂笔记 |
| `data/_startup.log` | 打包版启动路径自检（`PROJECT_ROOT` / `DATA_DIR`） |

编辑关键词文件后，重启监控或调用 `/api/reload_keywords` 即可生效。

## 🎛️ 设置面板

前端「设置」按分组表单化，保存时通过 `POST /api/settings` 写回 `.env`：

| 分组 | 覆盖字段 |
| ------ | ------ |
| 模型与接口 | `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`SUMMARY_MAX_TOKENS`、`ASR_MODE`、`WEBSPEECH_LANG`、`API_PORT` |
| Seed-ASR | `SEED_ASR_APP_KEY`、`SEED_ASR_ACCESS_KEY`、`SEED_ASR_RESOURCE_ID`、`SEED_ASR_WS_URL` |
| 其余 | DashScope、WinASR 调优参数、录音参数 |

除表单字段外的原始配置会保留在高级文本域中，保存以 `# 其他原始配置` 标记为界，反复保存不会叠加注释。

**界面风格**（本地 `localStorage` 持久化，不写入 `.env`）：

- 背景主题：`ocean` / `sunset` / `forest` / `slate`
- 窗口圆角、外壳透明度、字体缩放

## ⚙️ 调试接口

后端启动后可访问：

- Swagger UI：<http://127.0.0.1:8765/docs>
- 健康检查：<http://127.0.0.1:8765/api/health>
- 麦克风检测：<http://127.0.0.1:8765/api/check_mic>

常用 API：

| 方法 | 路径 | 用途 |
| ------ | ------ | ------ |
| POST | `/api/start_monitor` | 开始监控（课程名 + 可选 cite 资料 + 可选 ASR 模型） |
| POST | `/api/stop_monitor` | 停止监控并自动生成课后总结 |
| POST | `/api/pause_monitor` / `/api/resume_monitor` | 暂停 / 恢复 |
| GET | `/api/monitor_status` | 查询监控与暂停状态 |
| POST | `/api/ingest_asr_text` | 接收浏览器 Web Speech 识别结果 |
| GET | `/api/transcript_snapshot` | 增量获取转录（`since_mtime`） |
| GET | `/api/cite_files` | 列出可引用资料 |
| GET/POST | `/api/keywords`、`/api/update_keywords`、`/api/reload_keywords` | 关键词查询 / 追加 / 热重载 |
| POST | `/api/emergency_rescue` | 救场主接口 |
| POST | `/api/catchup` | 进度总结主接口 |
| POST | `/api/catchup_chat` | 进度追问 |
| POST | `/api/emergency_rescue_chat` | 救场追问 |
| POST | `/api/generate_summary` | 生成课后总结 |
| POST | `/api/upload_ppt` | 上传并解析资料 |
| GET/POST | `/api/prompts`、`/api/prompts/select`、`/api/prompts/draft` | 提示词预设与草稿 |
| GET/POST | `/api/settings` | 读写 `.env` |
| WS | `/api/ws/alerts` | 实时警报推送（支持 `ping` / `pong` 心跳） |

## 📦 打包发布

```powershell
.\build.ps1            # 使用 app-ui/package.json 里的版本号
.\build.ps1 v2.0.3     # 指定版本（会写回 package.json）
```

### 版本号规则

**唯一来源是 `app-ui/package.json`**，其余位置全部「读取」：

| 位置 | 关系 |
| ------ | ------ |
| `app-ui/package.json` | **唯一来源（SSOT）**，改版本号只改这里 |
| `app-ui/src-tauri/tauri.conf.json` | `"version": "../package.json"`，Tauri 原生读取 |
| `app-ui/src-tauri/Cargo.toml` | Cargo 不支持外部引用，由 `build.ps1` 自动同步 |
| `app-ui/src-tauri/Cargo.lock` | cargo 自行更新 |

提升位数：

| 变更类型 | 位数 | 示例 |
| ------ | ------ | ------ |
| 修 bug | 第三位 | `2.0.2` → `2.0.3` |
| 功能优化完善 | 第二位 | `2.0.3` → `2.1.0` |
| 大功能新增 | 第一位 | `2.1.0` → `3.0.0` |

### 打包流程

`build.ps1` 会自动执行：

1. 同步版本号（`package.json` → `Cargo.toml`）。
2. 用 `.venv` 中的 PyInstaller 打包 FastAPI 后端。
3. 用 Tauri 构建桌面端 exe（`--no-bundle`，不分发 MSI/NSIS）。
4. 组装 `release/` 目录。
5. 把 `api-service/.env.example` 同步为 `release/backend/.env` 与 `.env.example`。
6. 用临时 `.env` 和独立端口 **18765** 做后端健康检查，结束后恢复正式配置。
7. 输出 `ClassFox-v<版本>-win-x64.zip`。

`release/` 根目录只保留一个 `课狐ClassFox.exe`，后端配置随包落盘，用户无需手动复制模板。

> ⚠️ **`release/` 会被脚本整体删除后重建，且已被 gitignore**。
> 打包前确认没有需要保留的本地数据。

## 📥 免开发环境使用

从 [Releases](https://github.com/Infe1/ClassAssistant/releases) 下载 zip，解压后双击 `课狐ClassFox.exe`。

`release/backend/.env` 已经写入试用配置。如果额度耗尽或想换成自己的服务，
直接在应用内「设置」面板修改并保存即可，无需手动编辑文件。

## 🩺 排查指引

| 现象 | 先看哪里 |
| ------ | ------ |
| AI 追问没有内容 | 后端日志中的 `[LLM空回复]` 行，会指出是工具调用 / 思维链占满 / 模型拒答 |
| 追问长时间转圈 | 是否超过 `LLM_TIMEOUT`；后端是否仍在运行 |
| 总结文件 0 字节 | 调大 `.env` 的 `SUMMARY_MAX_TOKENS`（思考型模型需 20000 以上） |
| 后端连不上 | 8765 端口是否被旧实例占用；`release/data/_startup.log` 确认数据目录 |
| ASR 不出字 | 先调 `/api/check_mic` 验证麦克风；确认 `ASR_MODE` 拼写与对应密钥 |
| Seed-ASR 反复写盘 | 检查是否只落 `definite` 分句 |
| 图标模糊 | `icon.ico` 是否含 40/48/64px；改动后需重新编译 Rust |

完整排查记录见 `docs/`：

- [`docs/AI追问无回复-排查与修复.md`](docs/AI追问无回复-排查与修复.md)
- [`docs/开发指南.md`](docs/开发指南.md)
- [`docs/release-v2.0.3.md`](docs/release-v2.0.3.md)

## 📝 更新说明

### v2.0.3

- **修复 AI 追问偶尔返回「当前没有可用回答」**：该提示表示请求成功但正文为空。
  此前三种互不相同的空回复原因被合并成同一句话，且日志中不留任何记录；
  现已分别记录（模型返回工具调用 / 思维链吃光 `max_tokens` / 模型拒答），便于直接定位。
- **修复追问可能长时间卡在「AI 思考中...」**：`fetch` 无超时叠加 SDK 默认 600 秒超时
  （重试 2 次，最坏可达 30 分钟），会让界面长时间无响应且按钮不可点。
  现后端超时收窄至 60 秒（`.env` 新增 `LLM_TIMEOUT` 可调），前端 24 处请求统一加入超时，
  超时后把提问放回输入框、可直接重发。
- **修复任务栏图标模糊**：`icon.ico` 原本只有 16/32/128/256 四种尺寸，
  缺少 125%/150%/200% 缩放所需的 40/48/64px，只能放大 32px 显示。
  现补全为 16/24/32/48/64/128/256 七种尺寸，并统一改为 PNG 格式。
- **新增 prompt 缓存命中日志**：日志输出 `[LLM缓存]` 行，用于观察前缀缓存策略效果。
- **调整请求内容顺序**：课程资料前置、转录后置，使公共前缀稳定以命中服务端前缀缓存（语义未变）。
- 版本号 2.0.2 → 2.0.3。

### v2.0.2

- 修复 AI 追问面板首条回答未被滚动条囊括的问题。
- 版本号收敛为单一来源（`app-ui/package.json`），`tauri.conf.json` 改为路径引用。

### v2.0.1（Akurisu 改进）

- **修复长课堂总结写出 0 字节文件**：根因是思考型模型的思维链吃光 `max_tokens`，正文为空；
  且异常被自身 `except` 吞掉，反而写出一份内容全是报错的「假笔记」。
  - `max_tokens` 4000 → 20000，并支持用 `.env` 的 `SUMMARY_MAX_TOKENS` 覆盖，改完即生效、无需改代码。
  - 空正文 / 调用失败一律抛出异常，不再伪造成笔记；写盘前再兜底校验，失败不落盘。
- **设置面板新增「总结最大 token」**，可在界面内直接调整。
- **修复设置保存会重复叠加注释**：改为以 `# 其他原始配置` 标记为界，反复保存不再叠层（幂等）。
- **新增四角 L 形描边**（边角美术装饰）。
- **警报弹窗「查看」后不再彻底清除**：改为「挂起」，AI 面板关闭后自动恢复原警示状态。
- **窗口尺寸统一由 `App.tsx` 管理**，修复两处同时 `setSize` 导致警报弹层被压扁的竞态。
- 版本号 1.2.0 → 2.0.1。

### v1.3.0

- 合并上游 WinRT ASR 桥接（`winasr`）相关改动。

### v1.2.0

- 品牌名更新为 课狐 ClassFox，默认窗口标题与发布包名称同步调整。
- 发布目录改为单 exe 入口，内置启动后端，减少首次使用误操作。
- 新增课狐启动动画遮罩，启动阶段提供更明确的状态反馈。
- 救场与进度面板的返回区整体上移，适配当前更小的悬浮窗尺寸。
- 告警关键词判定改为只看当前新增行，修复跨行历史误报。
- Local ASR 调整停顿阈值并加入短时片段拼接，缓解本地识别只落前几个字的问题。
- 设置面板底部操作区再次上移，避免保存/取消按钮被底部边框遮挡。
- `release/backend/.env` 现在直接由 `.env.example` 构建，试用 key 可随包即用。

### v1.0.1

- 重构流式转录逻辑，解决 Seed-ASR 重复写盘和标点碎片问题。
- 增加 50 行滚动摘要压缩，降低长课堂上下文膨胀。
- 开始监控前新增课程名与 cite 资料选择面板。
- 资料上传改为保存到 `data/cite`，由用户在启动监控时选择引用。
- 新增设置面板，可直接读写后端 `.env`。
- `dev.bat`、`启动.bat` 和 Tauri 退出流程都增加旧后端清理逻辑。
- 打包脚本增加发布后端健康检查。

## License

MIT

本项目基于 [ouyangyipeng/ClassAssistant](https://github.com/ouyangyipeng/ClassAssistant)（MIT）持续维护。
