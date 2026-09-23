/**
 * API 服务模块
 * ============
 * 封装所有与 FastAPI 后端的 HTTP 通信
 */

// 后端地址（开发环境）
export const API_BASE = "http://127.0.0.1:8765/api";

/**
 * 默认请求超时（毫秒）。
 *
 * 为什么需要：`fetch` 本身没有超时。如果后端某一请求长时间不返回
 * （例如 uvicorn 单 worker 被一个慢 LLM 调用占住，事件循环无法调度其他请求），
 * 前端会永远停在「AI 思考中...」——按钮一直是 disabled，只能重启应用。
 * 有了超时，至少会自动结束并给出可读的报错。
 *
 * 超时值选择：比后端 LLM 超时（默认 60 秒）留足余量，避免前端先于后端放弃。
 */
const DEFAULT_TIMEOUT_MS = 90_000;

/** 课后总结可能很慢（长转录 + 思考型模型），单独放宽。 */
const SUMMARY_TIMEOUT_MS = 180_000;

function withTimeout(signal: AbortSignal | undefined, ms: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

/** 统一的错误信息：把 AbortError 翻译成人话。 */
function describeFailure(err: unknown, fallback: string): string {
  if (err instanceof DOMException && err.name === "AbortError") {
    return "请求超时：后端长时间未响应。请检查后端是否仍在运行，再重试一次。";
  }
  return err instanceof Error ? err.message : fallback;
}

/** 带超时的 fetch —— 所有后端请求都应经由它发出。 */
async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const { signal, clear } = withTimeout(init.signal ?? undefined, timeoutMs);
  try {
    // 注意：这里必须调用原生 fetch。曾误写成 fetchWithTimeout(...) 造成自递归，
    // 抛 RangeError: Maximum call stack size exceeded，导致所有后端请求全部失败。
    return await fetch(url, { ...init, signal });
  } finally {
    clear();
  }
}

/**
 * 上传 PPT 文件到后端进行解析
 */
export async function uploadPPT(file: File): Promise<{
  status: string;
  message: string;
  text_length: number;
  cite_filename: string;
}> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetchWithTimeout(`${API_BASE}/upload_ppt`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "上传失败");
  }
  return res.json();
}

export interface StartMonitorPayload {
  course_name: string;
  cite_filename?: string | null;
}

export interface StopMonitorResponse {
  status: string;
  message: string;
  summary?: {
    filename: string;
    course_name: string;
  };
  summary_error?: string;
}

export interface StartMonitorResponse {
  status: string;
  message: string;
  effective_asr_mode?: string;
  webspeech_lang?: string;
}

/**
 * 启动摸鱼监控模式
 */
export async function startMonitor(
  payload: StartMonitorPayload
): Promise<StartMonitorResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/start_monitor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("启动监控失败");
  const data = await res.json();
  if (data.status && data.status !== "started") {
    throw new Error(data.message || "启动监控失败");
  }
  return data;
}

/**
 * 停止监控
 */
export async function stopMonitor(): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/stop_monitor`, { method: "POST" });
  if (!res.ok) throw new Error("停止监控失败");
  return res.json();
}

export async function pauseMonitor(): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/pause_monitor`, { method: "POST" });
  if (!res.ok) throw new Error("暂停监控失败");
  return res.json();
}

export async function resumeMonitor(): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/resume_monitor`, { method: "POST" });
  if (!res.ok) throw new Error("继续监控失败");
  return res.json();
}

export async function stopMonitorWithSummary(): Promise<StopMonitorResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/stop_monitor`, { method: "POST" });
  if (!res.ok) throw new Error("停止监控失败");
  return res.json();
}

/**
 * 紧急救场 - 获取课堂上下文、问题和答案
 */
export async function emergencyRescue(): Promise<{
  status: string;
  context: string;
  question: string;
  answer: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/emergency_rescue`, { method: "POST" });
  if (!res.ok) throw new Error("救场请求失败");
  return res.json();
}

export async function emergencyRescueWithPrompt(payload: {
  preset_id?: string;
  prompt_override?: string;
}): Promise<{
  status: string;
  context: string;
  question: string;
  answer: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/emergency_rescue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("救场请求失败");
  return res.json();
}

export async function emergencyRescueChat(payload: {
  context: string;
  question: string;
  answer: string;
  followup: string;
  history: Array<{ role: string; content: string }>;
  preset_id?: string;
  prompt_override?: string;
}): Promise<{
  status: string;
  answer: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/emergency_rescue_chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch((err) => {
    throw new Error(describeFailure(err, "救场追问失败"));
  });
  if (!res.ok) throw new Error("救场追问失败");
  return res.json();
}

/**
 * 生成课后总结
 */
export async function generateSummary(): Promise<{
  status: string;
  filename: string;
  summary: string;
}> {
  const res = await fetchWithTimeout(
    `${API_BASE}/generate_summary`,
    { method: "POST" },
    SUMMARY_TIMEOUT_MS
  );
  if (!res.ok) throw new Error("生成总结失败");
  return res.json();
}

/**
 * 老师讲到哪了 - 获取课堂进度摘要
 */
export async function catchup(): Promise<{
  status: string;
  summary: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/catchup`, { method: "POST" });
  if (!res.ok) throw new Error("获取进度失败");
  return res.json();
}

export async function catchupWithPrompt(payload: {
  preset_id?: string;
  prompt_override?: string;
}): Promise<{
  status: string;
  summary: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/catchup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("获取进度失败");
  return res.json();
}

export async function catchupChat(payload: {
  summary: string;
  question: string;
  history: Array<{ role: string; content: string }>;
  preset_id?: string;
  prompt_override?: string;
}): Promise<{
  status: string;
  answer: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/catchup_chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch((err) => {
    throw new Error(describeFailure(err, "课堂追问失败"));
  });
  if (!res.ok) throw new Error("课堂追问失败");
  return res.json();
}

/**
 * 更新自定义关键词
 */
export async function updateKeywords(keywords: string[]): Promise<{
  status: string;
  all_keywords: string[];
}> {
  const res = await fetchWithTimeout(`${API_BASE}/update_keywords`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keywords }),
  });
  if (!res.ok) throw new Error("更新关键词失败");
  return res.json();
}

/**
 * 获取当前关键词列表
 */
export async function getKeywords(): Promise<{
  builtin: string[];
  custom: string[];
  all: string[];
}> {
  const res = await fetchWithTimeout(`${API_BASE}/keywords`);
  if (!res.ok) throw new Error("获取关键词失败");
  return res.json();
}

export async function getCiteFiles(): Promise<{
  status: string;
  items: Array<{ filename: string; updated_at: string; size: number }>;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/cite_files`);
  if (!res.ok) throw new Error("获取资料列表失败");
  return res.json();
}

export async function getSettings(): Promise<{
  status: string;
  content: string;
  path: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/settings`);
  if (!res.ok) throw new Error("读取设置失败");
  return res.json();
}

export async function ingestAsrText(payload: {
  text: string;
  is_final?: boolean;
}): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/ingest_asr_text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: payload.text,
      is_final: payload.is_final ?? true,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "注入语音文本失败");
  }

  const data = await res.json();
  if (data.status && data.status !== "success") {
    throw new Error(data.message || "注入语音文本失败");
  }

  return data;
}

export async function saveSettings(content: string): Promise<{
  status: string;
  message: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "保存设置失败");
  }
  return res.json();
}

export interface PromptPresetItem {
  id: string;
  name: string;
  description: string;
  content: string;
}

export interface PromptSnapshotResponse {
  status: string;
  data: {
    presets: Record<string, PromptPresetItem[]>;
    selected: Record<string, string>;
    custom_drafts: Record<string, string>;
  };
}

export async function getPrompts(category?: string): Promise<PromptSnapshotResponse> {
  const url = category
    ? `${API_BASE}/prompts?category=${encodeURIComponent(category)}`
    : `${API_BASE}/prompts`;
  const res = await fetchWithTimeout(url);
  if (!res.ok) throw new Error("获取提示词预设失败");
  return res.json();
}

export async function selectPromptPreset(payload: {
  category: string;
  preset_id: string;
}): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/prompts/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("切换提示词预设失败");
  return res.json();
}

export async function savePromptDraft(payload: {
  category: string;
  content: string;
}): Promise<{
  status: string;
  data: { category: string; content: string };
}> {
  const res = await fetchWithTimeout(`${API_BASE}/prompts/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("保存提示词草稿失败");
  return res.json();
}

export async function getTranscriptSnapshot(sinceMtime?: number): Promise<{
  status: string;
  exists: boolean;
  changed: boolean;
  mtime: number | null;
  line_count: number;
  sha1: string;
  content: string;
}> {
  const url = sinceMtime
    ? `${API_BASE}/transcript_snapshot?since_mtime=${encodeURIComponent(String(sinceMtime))}`
    : `${API_BASE}/transcript_snapshot`;
  const res = await fetchWithTimeout(url);
  if (!res.ok) throw new Error("获取转录快照失败");
  return res.json();
}
