/**
 * 上课摸鱼搭子 - 主应用组件
 * =========================
 * 整合所有子组件，管理全局状态
 */

import { useCallback, useEffect, useRef, useState } from "react";
import TitleBar from "./components/TitleBar";
import ToolBar from "./components/ToolBar";
import AlertOverlay from "./components/AlertOverlay";
import StartMonitorPanel from "./components/StartMonitorPanel";
import SettingsPanel from "./components/SettingsPanel";
import TranscriptViewer from "./components/TranscriptViewer";
import InlineAIChat from "./components/InlineAIChat";
import ToastContainer, { type ToastMessage } from "./components/Toast";
import { useWebSocket } from "./hooks/useWebSocket";
import classFoxIcon from "../src-tauri/icons/icon.png";
import {
  uploadPPT,
  startMonitor,
  pauseMonitor,
  resumeMonitor,
  stopMonitorWithSummary,
} from "./services/api";
import { applyUiStyleSettings, readUiStyleSettings } from "./services/preferences";
import { createBrowserAsrSession, type BrowserAsrSession } from "./services/browserAsr";

// Toast ID 计数器
let toastId = 0;

function isBrowserAsrMode(mode: string) {
  return mode === "webspeech" || mode === "edge-webspeech" || mode === "browser";
}

function SplashScreen() {
  return (
    <div className="splash-scene flex h-full w-full items-center justify-center bg-transparent">
      <div className="startup-card flex flex-col items-center bg-transparent px-6 py-5 text-center">
        <div className="startup-ring mb-4 flex h-24 w-24 items-center justify-center rounded-full border border-cyan-300/20 bg-white/6">
          <img src={classFoxIcon} alt="课狐 ClassFox" className="startup-logo h-14 w-14 object-contain" />
        </div>
        <p className="text-base font-semibold tracking-[0.18em] text-white/92">课狐启动中</p>
        <p className="mt-2 text-[11px] leading-6 text-cyan-50/70">ClassFox — Hears what you miss.</p>
      </div>
    </div>
  );
}

function MainApp() {
  // ---- 状态管理 ----
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showStartMonitorPanel, setShowStartMonitorPanel] = useState(false);
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const [toolbarMoreExpanded, setToolbarMoreExpanded] = useState(false);
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);
  const [aiExpanded, setAiExpanded] = useState(false);
  const [aiMode, setAiMode] = useState<"catchup" | "rescue">("catchup");
  const [citeRefreshToken, setCiteRefreshToken] = useState(0);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [activeCourseName, setActiveCourseName] = useState("");
  const [alertSuspended, setAlertSuspended] = useState(false);
  const browserAsrSessionRef = useRef<BrowserAsrSession | null>(null);
  const activeAsrModeRef = useRef("local");
  const activeBrowserAsrLangRef = useRef("zh-CN");

  // WebSocket 连接
  const { lastAlert, alertActive, connect, disconnect, dismissAlert } =
    useWebSocket();

  // 用户点「查看」后，警报不真正消失，只是被 AI 面板顶下去；
  // alertSuspended=true 时隐藏弹层，面板关闭后自动恢复原来的警示状态。
  const alertVisible = alertActive && !alertSuspended;

  useEffect(() => {
    applyUiStyleSettings(readUiStyleSettings());
  }, []);

  useEffect(() => {
    if (showStartMonitorPanel || showSettingsPanel) return;

    (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        const { LogicalSize } = await import("@tauri-apps/api/dpi");
        const win = getCurrentWindow();

        let width = 320;
        let height = toolbarMoreExpanded ? 210 : 80;

        if (transcriptExpanded) {
          height = Math.max(height, 430);
        }
        if (aiExpanded) {
          width = 900;
          height = Math.max(height, 520);
        }
        if (transcriptExpanded && aiExpanded) {
          height = Math.max(height, 580);
        }
        if (alertVisible && !aiExpanded) {
          height = Math.max(height, 160);
        }

        await win.setSize(new LogicalSize(width, height));
      } catch {
        /* 忽略窗口操作错误 */
      }
    })();
  }, [toolbarMoreExpanded, transcriptExpanded, aiExpanded, alertVisible, showStartMonitorPanel, showSettingsPanel]);

  // ---- Toast 管理 ----
  const addToast = useCallback(
    (text: string, type: ToastMessage["type"] = "info") => {
      const id = ++toastId;
      setToasts((prev) => [...prev, { id, text, type }]);
    },
    []
  );

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const stopBrowserAsrSession = useCallback(async () => {
    const session = browserAsrSessionRef.current;
    browserAsrSessionRef.current = null;
    if (session) {
      await session.stop();
    }
  }, []);

  const startBrowserAsrSession = useCallback(async () => {
    await stopBrowserAsrSession();
    const session = createBrowserAsrSession((message) => {
      addToast(message, message.includes("失败") || message.includes("错误") ? "error" : "info");
    }, { lang: activeBrowserAsrLangRef.current });
    browserAsrSessionRef.current = session;
    await session.start();
  }, [addToast, stopBrowserAsrSession]);

  // ---- 上传 PPT ----
  const handleUpload = useCallback(
    async (file: File) => {
      setIsLoading(true);
      try {
        const res = await uploadPPT(file);
        addToast(res.message, "success");
        setCiteRefreshToken((prev) => prev + 1);
      } catch (err) {
        addToast(
          `上传失败: ${err instanceof Error ? err.message : "未知错误"}`,
          "error"
        );
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  // ---- 开始/停止摸鱼 ----
  const handleStopMonitor = useCallback(async () => {
    setIsLoading(true);
    try {
      await stopBrowserAsrSession();
      const res = await stopMonitorWithSummary();
      disconnect();
      dismissAlert();          // 必须清除警报状态：disconnect() 不会重置 alertActive，
      setIsMonitoring(false);  // 否则停止监听后警报弹层会残留在屏幕上。
      setIsPaused(false);
      setAlertSuspended(false);
      setActiveCourseName("");
      activeAsrModeRef.current = "local";
      setTranscriptExpanded(false);
      setAiExpanded(false);
      addToast(res.message, "info");
      if (res.summary?.filename) {
        addToast(`已自动生成总结: ${res.summary.filename}`, "success");
      } else if (res.summary_error) {
        addToast(res.summary_error, "error");
      }
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        const { LogicalSize } = await import("@tauri-apps/api/dpi");
        await getCurrentWindow().setSize(new LogicalSize(320, 80));
      } catch {
        /* 忽略窗口操作错误 */
      }
    } catch (err) {
      addToast(
        `操作失败: ${err instanceof Error ? err.message : "未知错误"}`,
        "error"
      );
    } finally {
      setIsLoading(false);
    }
  }, [disconnect, dismissAlert, addToast, stopBrowserAsrSession]);

  const handleOpenStartMonitor = useCallback(() => {
    setShowStartMonitorPanel(true);
  }, []);

  const handlePauseResume = useCallback(async () => {
    setIsLoading(true);
    try {
      if (isPaused) {
        const res = await resumeMonitor();
        try {
          if (isBrowserAsrMode(activeAsrModeRef.current)) {
            await startBrowserAsrSession();
          }
          connect();
          setIsPaused(false);
          addToast(res.message, "success");
        } catch (resumeErr) {
          await pauseMonitor().catch(() => {
            /* ignore rollback failure */
          });
          throw resumeErr;
        }
      } else {
        const res = await pauseMonitor();
        if (isBrowserAsrMode(activeAsrModeRef.current)) {
          await stopBrowserAsrSession();
        }
        disconnect();
        setIsPaused(true);
        addToast(res.message, "info");
      }
    } catch (err) {
      addToast(
        `操作失败: ${err instanceof Error ? err.message : "未知错误"}`,
        "error"
      );
    } finally {
      setIsLoading(false);
    }
  }, [isPaused, connect, disconnect, addToast, startBrowserAsrSession, stopBrowserAsrSession]);

  const handleStartMonitorConfirm = useCallback(
    async ({
      courseName,
      citeFilename,
    }: {
      courseName: string;
      citeFilename: string | null;
    }) => {
      let backendStarted = false;

      try {
        const result = await startMonitor({
          course_name: courseName,
          cite_filename: citeFilename,
        });
        backendStarted = true;

        const effectiveAsrMode = result.effective_asr_mode || "local";
        const effectiveWebspeechLang = result.webspeech_lang || "zh-CN";
        activeAsrModeRef.current = effectiveAsrMode;
        activeBrowserAsrLangRef.current = effectiveWebspeechLang;

        if (isBrowserAsrMode(effectiveAsrMode)) {
          await startBrowserAsrSession();
        }

        connect();
        setIsMonitoring(true);
        setIsPaused(false);
        setActiveCourseName(courseName);
        setShowStartMonitorPanel(false);
        addToast(courseName ? `开始摸鱼模式 🎣 ${courseName}` : "开始摸鱼模式 🎣", "success");
      } catch (err) {
        activeAsrModeRef.current = "local";
        await stopBrowserAsrSession();
        if (backendStarted) {
          try {
            await stopMonitorWithSummary();
          } catch {
            /* ignore cleanup failures */
          }
        }
        throw err;
      }
    },
    [connect, addToast, startBrowserAsrSession, stopBrowserAsrSession]
  );

  // ---- 救场 ----
  const handleRescue = useCallback(() => {
    // 不真正清除警报：先「挂起」，AI 面板关闭后自动恢复原来的警示状态
    setAlertSuspended(true);
    setAiMode("rescue");
    setTranscriptExpanded(true);
    setAiExpanded(true);
  }, []);

  // ---- 老师讲到哪了 ----
  const handleCatchup = useCallback(() => {
    // 同上：保留原来的警示状态，返回时重新弹出
    setAlertSuspended(true);
    setAiMode("catchup");
    setTranscriptExpanded(true);
    setAiExpanded(true);
  }, []);

  // AI 面板关闭后，若警报仍然有效，恢复显示原来的警示弹层
  useEffect(() => {
    if (!aiExpanded && alertSuspended && alertActive) {
      setAlertSuspended(false);
    }
  }, [aiExpanded, alertSuspended, alertActive]);

  // 真正忽略警报（清除状态，不再恢复）
  const handleDismissAlert = useCallback(() => {
    setAlertSuspended(false);
    dismissAlert();
  }, [dismissAlert]);

  const handleOpenSettings = useCallback(() => {
    setShowSettingsPanel(true);
  }, []);

  const handleCloseSettings = useCallback(() => {
    setShowSettingsPanel(false);
  }, []);

  return (
    <div className="app-shell relative flex h-full w-full flex-col overflow-hidden rounded-[var(--window-radius)] border border-[var(--theme-shell-border)] shadow-2xl backdrop-blur-xl">
      {/* 边角美术装饰层 */}
      <div className="corner-art" aria-hidden="true">
        <span className="corner corner--tl" />
        <span className="corner corner--tr" />
        <span className="corner corner--bl" />
        <span className="corner corner--br" />
        <span className="corner-sheen" />
      </div>

      {/* 标题栏 */}
      <div className="relative z-10">
        <TitleBar isMonitoring={isMonitoring} isPaused={isPaused} courseName={activeCourseName} />
      </div>

      <div className="relative z-10 flex min-h-0 flex-1 flex-col px-2 pb-2">
        {/* 工具栏 */}
        {!showStartMonitorPanel && !showSettingsPanel && (
          <ToolBar
            isMonitoring={isMonitoring}
            isPaused={isPaused}
            isLoading={isLoading}
            courseName={activeCourseName}
            onUpload={handleUpload}
            onStartMonitor={handleOpenStartMonitor}
            onStopMonitor={handleStopMonitor}
            onPauseResume={handlePauseResume}
            onCatchup={handleCatchup}
            onSettings={handleOpenSettings}
            transcriptExpanded={transcriptExpanded}
            aiExpanded={aiExpanded}
            onToggleTranscript={() => setTranscriptExpanded((prev) => !prev)}
            onToggleAI={() => {
              setAiMode("catchup");
              setAiExpanded((prev) => !prev);
            }}
            onMoreChange={setToolbarMoreExpanded}
          />
        )}

        {!showStartMonitorPanel && !showSettingsPanel && (transcriptExpanded || aiExpanded) && (
          <div className="mt-1 min-h-0 flex-1 overflow-hidden">
            <div className={`grid h-full min-h-0 gap-2 ${aiExpanded && transcriptExpanded ? "grid-cols-[38%_62%]" : "grid-cols-1"}`}>
              {transcriptExpanded && (
                <div className="min-h-0">
                  <TranscriptViewer title="课堂字幕" pollIntervalMs={5000} />
                </div>
              )}

              {aiExpanded && (
                <div className="min-h-0">
                  <InlineAIChat visible={aiExpanded} mode={aiMode} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <StartMonitorPanel
        visible={showStartMonitorPanel}
        onClose={() => setShowStartMonitorPanel(false)}
        onConfirm={handleStartMonitorConfirm}
        refreshToken={citeRefreshToken}
      />

      <SettingsPanel
        visible={showSettingsPanel}
        onClose={handleCloseSettings}
        onSaved={(message) => addToast(message, "success")}
      />

      {/* 点名警报覆盖层 */}
      <AlertOverlay
        active={alertVisible}
        level={lastAlert?.level ?? "danger"}
        keywords={lastAlert?.keywords ?? []}
        text={lastAlert?.text ?? ""}
        onRescue={handleRescue}
        onCatchup={handleCatchup}
        onDismiss={handleDismissAlert}
      />

      {/* Toast 提示 */}
      <ToastContainer messages={toasts} onRemove={removeToast} />
    </div>
  );
}

export default function App() {
  const [windowLabel, setWindowLabel] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;

    (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        if (!disposed) {
          setWindowLabel(getCurrentWindow().label);
        }
      } catch {
        if (!disposed) {
          setWindowLabel("main");
        }
      }
    })();

    return () => {
      disposed = true;
    };
  }, []);

  if (windowLabel === null) {
    return null;
  }

  if (windowLabel === "splash") {
    return <SplashScreen />;
  }
  return <MainApp />;
}
