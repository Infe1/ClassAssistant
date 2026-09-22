# 🦊 课狐 ClassFox - 你的上课摸鱼搭子 🐟

> 📚 项目文档：<https://ouyangyipeng.github.io/ClassAssistant/>

<!-- markdownlint-disable MD033 -->
<div align="center">
  <img src="docs/img/logo透明背景.png" alt="课狐 ClassFox Logo" width="128" />
  <br />
  <a href="https://github.com/ouyangyipeng/ClassAssistant/stargazers">
    <img src="https://img.shields.io/github/stars/ouyangyipeng/ClassAssistant?style=for-the-badge&logo=github" alt="GitHub stars" />
  </a>
  <a href="https://github.com/ouyangyipeng/ClassAssistant/issues">
    <img src="https://img.shields.io/github/issues/ouyangyipeng/ClassAssistant?style=for-the-badge&logo=github" alt="GitHub issues" />
  </a>
</div>
<!-- markdownlint-enable MD033 -->

> ClassFox — Hears what you miss.
>
> ClassFox 课狐 —— 听见你的错过，接住你的惊慌。
>
> 以耳廓狐为灵感的小体量课堂悬浮助手：资源占用轻，专门盯住你最容易错过的点名、提问和进度变化。

## 🚀 v1.2.0 近期优化

- **品牌升级**：项目产品名更新为“课狐 ClassFox”，强调“小体量 + 高听感”的课堂辅助定位。
- **单入口发布**：release 根目录只保留一个 课狐ClassFox.exe，后端由主程序静默拉起，避免首次使用误点多个入口。
- **启动体验升级**：新增居中启动遮罩与 logo 动画，启动阶段不再裸露命令行窗口。
- **紧凑悬浮窗**：主窗口压缩到更低调的 320 宽紧凑尺寸，监控、警报和扩展面板按场景单独控制高度。
- **追问链路补齐**：救场面板和“老师讲到哪了”都支持继续追问，返回区位置上移，避免在小窗里被截断。
- **关键词判定更准**：告警改为只检测当前新增落盘的那一行，避免把历史多行误拼成一次红灯命中。
- **Local 模式修正**：本地识别增加短时片段拼接与更保守的停顿判定，减少一句话只落前几个字的问题。
- **试用配置内置**：打包时会直接把 api-service/.env.example 构建为 release/backend/.env，方便开箱即用。

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
| 🎙️ 实时语音监控 | Local ASR / Windows Built-in ASR / Seed-ASR / DashScope / Mock 多模式切换 |
| 🧹 去重转录 | 流式识别结果按句落盘，过滤重复、碎片标点和相近修正文 |
| 🧠 转录保留策略 | 默认完整保留课堂转录，支持按开关启用滚动摘要压缩 |
| 🚨 点名预警 | 命中关键词后通过 WebSocket 推送红色警报弹层 |
| 🆘 一键救场 | 结合最近转录和课程资料，生成应答思路与参考答案 |
| 📍 老师讲到哪了 | 对最近课堂内容做即时进度总结 |
| 📝 课后总结 | 生成 Markdown 课堂笔记并落盘到 data/summaries |
| 📄 资料上传与引用 | PPT / PDF / Word 解析后存入 data/cite，开始监控前可选择引用资料 |
| ⚙️ 内置设置面板 | 前端可直接编辑后端 .env，无需手动找文件 |

## 🏗️ 架构概览

```text
Tauri + React UI
        │
        ├─ HTTP API
        └─ WebSocket Alert
                │
          FastAPI Backend
                │
      ┌─────────┼─────────┐
      │         │         │
    ASR       LLM     Transcript
      │                   │
  Local / Seed /      class_transcript.txt
  DashScope / Mock    current_class_material.txt
                      data/cite/*.txt
```

后端负责录音、ASR、关键词检测、转录落盘和 LLM 调用；前端负责悬浮窗 UI、警报展示、资料上传、监控启动参数选择和设置编辑。

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/ouyangyipeng/ClassAssistant.git
cd ClassAssistant
```

### 2. 配置后端 Python 环境

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

### 4. 配置环境变量

在 api-service 下创建 .env，可参考 .env.example：

```env
# ASR 模式: local | windows | mock | dashscope | seed-asr
ASR_MODE=local

# 转录策略: 0=完整保留, 1=滚动压缩
TRANSCRIPT_ENABLE_ROLLING_SUMMARY=0

# Seed-ASR
SEED_ASR_APP_KEY=your_app_key
SEED_ASR_ACCESS_KEY=your_access_key
SEED_ASR_RESOURCE_ID=volc.bigasr.sauc.duration

# DashScope Fun-ASR
DASHSCOPE_API_KEY=sk-your-dashscope-key

# LLM
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your-key
LLM_MODEL=deepseek-chat

# Audio
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_CHUNK_SIZE=3200
```

### 5. 启动开发模式

推荐直接运行根目录的 dev.bat。

它现在会先清理以下残留状态，再启动开发后端和 Tauri 前端：

- 上一次残留的 class-assistant-backend.exe
- 标题为 ClassAssistant-Backend 的开发后端终端
- 监听 8765 端口的旧进程

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

1. 点击“上传资料”，将 PPT / PDF / Word 解析为可引用文本。
2. 点击“开始摸鱼”，在启动面板里填写课程名称，并可选择一份 cite 资料。
3. 后端开始监听课堂音频，按句落盘到 data/class_transcript.txt。
4. 命中关键词时，前端立即显示警报弹层。
5. 需要时点击“救场”或“老师讲到哪了”，调用 LLM 生成结果。
6. 下课后点击“总结”，生成 Markdown 笔记。

## 🎙️ ASR 模式说明

| 模式 | 说明 |
| ------ | ------ |
| local | 基于 SpeechRecognition + Google Speech API，按句回调，适合直接体验 |
| windows | Windows 内置语音识别（WinRT SpeechRecognizer），优先使用本机能力 |
| winasr | C# + WinRT 原生控制台桥接，适合 Windows 桌面环境 |
| mock | 不录音、不识别，适合纯 UI 联调 |
| dashscope | 阿里云百炼 Fun-ASR |
| seed-asr | 字节 Seed-ASR，使用 utterances + definite 分句，避免流式累积文本反复写盘 |

### 当前转录策略

- Local ASR 继续保持“识别完一句追加一行”的本地模式。
- Seed-ASR 只把 definite 的稳定句子落盘，partial 文本只保存在内存中。
- 会过滤孤立标点、极短碎片和与近期内容高度相似的重复句。
- 默认完整保留课堂转录，不做滚动压缩，便于回看和阅读。
- 如需减少上下文体积，可将 TRANSCRIPT_ENABLE_ROLLING_SUMMARY 设为 1，按 50 条触发一次滚动摘要。

## 📁 运行时数据

| 路径 | 用途 |
| ------ | ------ |
| data/class_transcript.txt | 当前课堂完整记录（默认不压缩；开启开关后含历史摘要块） |
| data/current_class_material.txt | 当前选中的参考资料文本 |
| data/cite/ | 上传资料解析后的候选引用文本 |
| data/keywords.txt | 用户自定义关键词 |
| data/summaries/ | 生成的课堂笔记 |

## ⚙️ 调试接口

后端启动后可访问：

- Swagger UI: <http://127.0.0.1:8765/docs>
- 健康检查: <http://127.0.0.1:8765/api/health>
- 麦克风检测: <http://127.0.0.1:8765/api/check_mic>

常用 API：

- POST /api/start_monitor
- POST /api/stop_monitor
- GET /api/cite_files
- GET /api/settings
- POST /api/settings
- POST /api/emergency_rescue
- POST /api/catchup
- POST /api/generate_summary

## 📦 打包发布

```powershell
./build.ps1 v1.2.0
```

打包流程会自动执行：

1. 同步前后端版本号。
2. 用 .venv 中的 PyInstaller 打包 FastAPI 后端。
3. 用 Tauri 构建桌面端 exe。
4. 组装 release 目录。
5. 把 api-service/.env.example 同步到 release/backend/.env 与 .env.example。
6. 用临时 .env 和独立端口 18765 做后端健康检查，结束后恢复正式配置。
7. 输出 zip 压缩包。

release 根目录现在只保留一个 课狐ClassFox.exe；后端配置会随安装包一起落到 backend/.env，用户无需再手动复制模板。

## 📥 免开发环境使用

从 Releases 下载 zip，解压后双击 课狐ClassFox.exe。

release/backend/.env 默认已经写入试用配置；如果额度耗尽或你要切换成自己的服务，直接在应用内“设置”面板修改并保存即可。

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ouyangyipeng/ClassAssistant&type=Date)](https://star-history.com/#ouyangyipeng/ClassAssistant&Date)

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

### v2.0.1（Akurisu 改进）

- **修复长课堂总结写出 0 字节文件**：根因是思考型模型的思维链吃光 `max_tokens`，正文为空；且异常被自身 `except` 吞掉，反而写出一份内容全是报错的「假笔记」。
  - `max_tokens` 4000 → 20000，并支持用 `.env` 的 `SUMMARY_MAX_TOKENS` 覆盖，改完即生效、无需改代码。
  - 空正文 / 调用失败一律抛出异常，不再伪造成笔记；写盘前再兜底校验，失败不落盘。
- **设置面板新增「总结最大 token」**，可在界面内直接调整。
- **修复设置保存会重复叠加注释**：改为以 `# 其他原始配置` 标记为界，反复保存不再叠层（幂等）。
- **新增四角 L 形描边**（边角美术装饰）。
- **警报弹窗「查看」后不再彻底清除**：改为「挂起」，AI 面板关闭后自动恢复原警示状态。
- **窗口尺寸统一由 `App.tsx` 管理**，修复两处同时 `setSize` 导致警报弹层被压扁的竞态。
- 版本号 1.2.0 → 2.0.1。

### v1.2.0

- 品牌名更新为 课狐 ClassFox，默认窗口标题与发布包名称同步调整。
- 发布目录改为单 exe 入口，内置启动后端，减少首次使用误操作。
- 新增课狐启动动画遮罩，启动阶段提供更明确的状态反馈。
- 救场与进度面板的返回区整体上移，适配当前更小的悬浮窗尺寸。
- 告警关键词判定改为只看当前新增行，修复跨行历史误报。
- Local ASR 调整停顿阈值并加入短时片段拼接，缓解本地识别只落前几个字的问题。
- 设置面板底部操作区再次上移，避免保存/取消按钮被底部边框遮挡。
- release/backend/.env 现在直接由 .env.example 构建，试用 key 可随包即用。

### v1.0.1

- 重构流式转录逻辑，解决 Seed-ASR 重复写盘和标点碎片问题。
- 增加 50 行滚动摘要压缩，降低长课堂上下文膨胀。
- 开始监控前新增课程名与 cite 资料选择面板。
- 资料上传改为保存到 data/cite，由用户在启动监控时选择引用。
- 新增设置面板，可直接读写后端 .env。
- dev.bat、启动.bat 和 Tauri 退出流程都增加旧后端清理逻辑。
- 打包脚本增加发布后端健康检查，当前已可成功产出 v1.0.1 压缩包。

## License

MIT
