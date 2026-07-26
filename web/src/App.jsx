import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_API,
  FALLBACK_OPTS,
  getHealth,
  getOptions,
  postPreprocess,
  postOcr,
  postOcrPostprocess,
  dataUrlToBlob,
  postLogin,
  postRegister,
  postGoogleLogin,
  getDocuments,
  getDocument,
  createDocument,
  updateDocument,
  deleteDocument,
  fetchAuthenticatedImage,
} from "./api.js";
import {
  normalizeRaw,
  mergeAI,
  isPostprocessFallback,
  applyGlyphEdit,
  applyLineEdit,
  resultStats,
  toPlainResult,
} from "./ocr.js";
import { ToastStack, ConfirmDialog, Modal, Spinner } from "./ui.jsx";
import Header from "./components/Header.jsx";
import SettingsModal from "./components/SettingsModal.jsx";
import AuthModal from "./components/AuthModal.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import ViewerPanel from "./components/ViewerPanel.jsx";
import ProofPanel from "./components/ProofPanel.jsx";

const DEFAULT_PARAMS = {
  preprocess: true,
  stage: "flipped",
  resize_width: 1600,
  canny_low: 30,
  canny_high: 120,
  deskew_range: 15,
  clahe_clip: 3,
  clahe_tile: 8,
  noise_method: "bilateral",
  flip: "horizontal",
};

function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

let toastSeq = 0;

export default function App() {
  // --- Giao diện chung ---
  const [theme, setTheme] = useState(initTheme);
  const [activeTab, setActiveTab] = useState("ocr");
  const [toasts, setToasts] = useState([]);
  const [confirmState, setConfirmState] = useState(null); // {title,message,onConfirm}

  // --- Máy chủ ---
  const [apiBase, setApiBase] = useState(localStorage.getItem("apiBase") || DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [serverOpts, setServerOpts] = useState(FALLBACK_OPTS);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // --- OCR ---
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [useAI, setUseAI] = useState(localStorage.getItem("useAI") !== "0");
  const [file, setFile] = useState(null);
  const [imgUrl, setImgUrl] = useState(null);
  const [preResult, setPreResult] = useState(null); // {image, meta}
  const [result, setResult] = useState(null); // dạng chuẩn hoá trong ocr.js
  const [phase, setPhase] = useState(null); // null | 'pre' | 'ocr' | 'ai'
  const [error, setError] = useState(null);
  const [elapsedMs, setElapsedMs] = useState(null);

  const [view, setView] = useState("processed");
  const [resultView, setResultView] = useState("columns");
  const [aiView, setAiView] = useState("final");
  const [showBoxes, setShowBoxes] = useState(true);
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null); // {recIdx, glyphIdx}
  // Tỷ lệ bề rộng panel ảnh (%) — kéo splitter giữa 2 panel để chỉnh
  const [split, setSplit] = useState(() => {
    const v = parseFloat(localStorage.getItem("workspaceSplit"));
    return Number.isFinite(v) && v >= 25 && v <= 75 ? v : 53;
  });
  const workspaceRef = useRef(null);

  // --- Tài khoản & lịch sử ---
  const [token, setToken] = useState(localStorage.getItem("token") || null);
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "null");
    } catch {
      return null;
    }
  });
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authError, setAuthError] = useState(null);
  const [historyDocs, setHistoryDocs] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");
  const [savingDoc, setSavingDoc] = useState(false);

  const fileInputRef = useRef(null);
  // Epoch chống race: tăng mỗi khi ngữ cảnh ảnh/tài liệu đổi (chọn ảnh mới,
  // bỏ ảnh, mở tài liệu). Chuỗi async đang chạy so sánh trước khi setState
  // để kết quả cũ không đè lên ngữ cảnh mới.
  const runSeqRef = useRef(0);

  // --- Toast helpers ---
  const pushToast = useCallback((kind, title, sub) => {
    const id = ++toastSeq;
    setToasts((t) => [...t, { id, kind, title, sub }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const dismissToast = (id) => setToasts((t) => t.filter((x) => x.id !== id));

  // --- Theme ---
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("useAI", useAI ? "1" : "0");
  }, [useAI]);

  // --- Máy chủ: health + options ---
  const checkHealth = useCallback(async (base = apiBase) => {
    setHealth("checking");
    try {
      setHealth((await getHealth(base)) ? "ok" : "down");
    } catch {
      setHealth("down");
    }
    try {
      setServerOpts(await getOptions(base));
    } catch {
      /* giữ fallback */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  useEffect(() => {
    checkHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  // Chỉ ghi localStorage khi người dùng chủ động đổi trong Cài đặt — không
  // ghim giá trị mặc định/VITE_API_BASE ngay lần truy cập đầu.
  const changeApiBase = (base) => {
    setApiBase(base);
    localStorage.setItem("apiBase", base);
  };

  // --- Đăng nhập / đăng xuất ---
  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    setHistoryDocs([]);
    setSelectedDocId(null);
    setActiveTab("ocr");
  }, []);

  const applyLoginResponse = (j) => {
    localStorage.setItem("token", j.access_token);
    localStorage.setItem("user", JSON.stringify(j.user));
    setToken(j.access_token);
    setUser(j.user);
    setAuthModalOpen(false);
    setAuthError(null);
    pushToast("success", `Chào ${j.user?.fullname || "bạn"}!`);
  };

  const handleAuthSubmit = async (form) => {
    setAuthError(null);
    try {
      if (authMode === "login") {
        applyLoginResponse(await postLogin(apiBase, form.email, form.password));
      } else {
        await postRegister(apiBase, form);
        pushToast("success", "Đăng ký thành công", "Hãy đăng nhập bằng tài khoản mới.");
        setAuthMode("login");
      }
    } catch (e) {
      setAuthError(e.message || String(e));
    }
  };

  const handleGoogleCredential = useCallback(
    async (credential) => {
      setAuthError(null);
      try {
        applyLoginResponse(await postGoogleLogin(apiBase, credential));
      } catch (e) {
        setAuthError(e.message || String(e));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [apiBase]
  );

  // Phiên hết hạn (401) ở bất kỳ thao tác tài liệu nào → đăng xuất + báo.
  const handleUnauthorized = (e) => {
    if (!e?.unauthorized) return false;
    handleLogout();
    pushToast("error", "Phiên đăng nhập hết hạn", "Vui lòng đăng nhập lại.");
    return true;
  };

  // --- Lịch sử ---
  const loadHistory = useCallback(async () => {
    if (!token) return;
    setHistoryLoading(true);
    try {
      setHistoryDocs(await getDocuments(apiBase, token));
    } catch (e) {
      if (e.unauthorized) {
        handleLogout();
        pushToast("error", "Phiên đăng nhập hết hạn", "Vui lòng đăng nhập lại.");
      } else {
        console.error(e);
      }
    } finally {
      setHistoryLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, token]);

  useEffect(() => {
    if (token) loadHistory();
  }, [token, loadHistory]);

  const openDocument = async (docId) => {
    const seq = ++runSeqRef.current;
    const stale = () => runSeqRef.current !== seq;
    setPhase("ocr");
    setError(null);
    setSelected(null);
    setHovered(null);
    try {
      const doc = await getDocument(apiBase, token, docId);
      if (stale()) return;

      const originalUrl = await fetchAuthenticatedImage(apiBase, token, doc.original_image_url);
      let ocrUrl = null;
      if (doc.ocr_image_url) {
        ocrUrl = await fetchAuthenticatedImage(apiBase, token, doc.ocr_image_url);
      }
      if (stale()) {
        // Người dùng đã bấm tài liệu/ảnh khác — hủy kết quả này, dọn URL.
        if (originalUrl) URL.revokeObjectURL(originalUrl);
        if (ocrUrl) URL.revokeObjectURL(ocrUrl);
        return;
      }
      if (!originalUrl) {
        pushToast("warn", "Không tải được ảnh gốc", "Vẫn hiển thị văn bản đã lưu.");
      }

      setSelectedDocId(doc.id);
      setSaveTitle(doc.title || "");
      setImgUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return originalUrl;
      });
      setFile({ name: doc.title || "Tài liệu lưu trữ", saved: true });

      const normalized = normalizeRaw(doc.ocr_result || {});
      normalized.ocr_image = ocrUrl;
      setResult(normalized);
      setElapsedMs(null);
      setPreResult(null);
      setView("processed");
      setAiView("final");
      setActiveTab("ocr");
    } catch (e) {
      if (!stale() && !handleUnauthorized(e)) {
        pushToast("error", "Không mở được tài liệu", e.message);
      }
    } finally {
      if (!stale()) setPhase(null);
    }
  };

  const requestDeleteDoc = (doc) => {
    setConfirmState({
      title: "Xóa tài liệu",
      message: `Xóa vĩnh viễn “${doc.title || `Tài liệu #${doc.id}`}” khỏi tài khoản?`,
      onConfirm: async () => {
        setConfirmState(null);
        try {
          await deleteDocument(apiBase, token, doc.id);
          if (selectedDocId === doc.id) {
            runSeqRef.current += 1;
            setSelectedDocId(null);
            setResult(null);
            setFile(null);
            setImgUrl((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return null;
            });
          }
          pushToast("success", "Đã xóa tài liệu");
          loadHistory();
        } catch (e) {
          if (!handleUnauthorized(e)) pushToast("error", "Không xóa được", e.message);
        }
      },
    });
  };

  // --- Chọn ảnh ---
  const onPickFile = (f, openDialog = false) => {
    if (!token) return; // màn khóa — phòng thủ thêm ngoài inert
    if (openDialog || f === undefined) {
      fileInputRef.current?.click();
      return;
    }
    if (!f) return;
    if (!f.type?.startsWith("image/")) {
      pushToast("error", "Tệp không hợp lệ", "Vui lòng chọn tệp hình ảnh.");
      return;
    }
    runSeqRef.current += 1; // hủy hiệu lực mọi chuỗi OCR đang chạy
    setPhase(null);
    setError(null);
    setResult(null);
    setElapsedMs(null);
    setPreResult(null);
    setSelectedDocId(null);
    setSelected(null);
    setHovered(null);
    setFile(f);
    setSaveTitle("");
    setImgUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
    setView("original");
  };

  const clearFile = () => {
    runSeqRef.current += 1;
    setPhase(null);
    setFile(null);
    setResult(null);
    setPreResult(null);
    setSelectedDocId(null);
    setSelected(null);
    setError(null);
    setElapsedMs(null);
    setImgUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  };

  // --- Tham số tiền xử lý ---
  const setParam = (k, v) => {
    setParams((p) => ({ ...p, [k]: v }));
    setPreResult(null);
  };

  // --- Tiền xử lý ---
  const runPreprocessOnly = async () => {
    if (!token || !file || file.saved) return null;
    const seq = runSeqRef.current;
    const stale = () => runSeqRef.current !== seq;
    setPhase("pre");
    setError(null);
    try {
      const pre = await postPreprocess(apiBase, file, params);
      if (stale()) return null;
      setPreResult(pre);
      setView("processed");
      return pre;
    } catch (e) {
      if (!stale()) setError(e.message || String(e));
      return null;
    } finally {
      if (!stale()) setPhase(null);
    }
  };

  // --- OCR (kèm hiệu đính AI nếu bật) ---
  const runOcr = async () => {
    if (!token || !file || file.saved) return;
    const seq = runSeqRef.current;
    const stale = () => runSeqRef.current !== seq;
    setError(null);
    setResult(null);
    setSelected(null);
    setHovered(null);
    const t0 = performance.now();
    try {
      // 1. Ảnh đầu vào cuối cùng (đã tiền xử lý nếu bật)
      let blob = file;
      let pre = null;
      if (params.preprocess) {
        pre = preResult;
        if (!pre) {
          pre = await runPreprocessOnly();
          if (!pre || stale()) return;
        }
        blob = await dataUrlToBlob(pre.image);
      }
      if (stale()) return;

      // 2. OCR gốc — luôn lấy độ tin cậy + ứng viên theo ký tự
      setPhase("ocr");
      const raw = await postOcr(apiBase, blob, "preprocessed.jpg");
      if (stale()) return;

      // 3. Hiệu đính SikuBERT (tùy chọn) rồi ghép với bản gốc.
      //    Bỏ qua khi không nhận dạng được chữ nào (không có gì để sửa).
      let merged;
      if (useAI && raw.results?.length) {
        setPhase("ai");
        try {
          const pp = await postOcrPostprocess(apiBase, blob, "preprocessed.jpg");
          if (stale()) return;
          if (isPostprocessFallback(pp)) {
            merged = normalizeRaw(raw);
            merged.ai = { requested: true, applied: false, fallback: true };
            pushToast(
              "warn",
              "SikuBERT chưa sẵn sàng",
              "Máy chủ trả về kết quả OCR gốc (mô hình hậu xử lý chưa nạp)."
            );
          } else {
            merged = mergeAI(raw, pp);
            if (merged.ai.changedCount === 0) {
              pushToast("info", "SikuBERT không tìm thấy lỗi cần sửa");
            }
          }
        } catch (e) {
          if (stale()) return;
          merged = normalizeRaw(raw);
          merged.ai = { requested: true, applied: false, fallback: true };
          pushToast("warn", "Hiệu đính AI thất bại", e.message);
        }
      } else {
        merged = normalizeRaw(raw);
      }
      if (stale()) return;

      // Giữ metadata tiền xử lý vào kết quả (để lưu/xuất không mất thông tin
      // ảnh đã qua pipeline nào — /ocr được gọi với preprocess=false).
      if (pre?.meta) {
        merged.preprocess = { applied: true, ...pre.meta };
      }

      setElapsedMs(Math.round(performance.now() - t0));
      setResult(merged);
      setAiView("final");
      setView("processed");
    } catch (e) {
      if (!stale()) setError(e.message || String(e));
    } finally {
      if (!stale()) setPhase(null);
    }
  };

  // --- Splitter chỉnh kích thước 2 panel ---
  const saveSplit = (v) => localStorage.setItem("workspaceSplit", String(v));

  const nudgeSplit = (delta) => {
    setSplit((v) => {
      const next = Math.min(75, Math.max(25, v + delta));
      saveSplit(next);
      return next;
    });
  };

  const resetSplit = () => {
    setSplit(53);
    saveSplit(53);
  };

  const onSplitterDown = (e) => {
    e.preventDefault();
    const el = workspaceRef.current;
    const splitter = e.currentTarget;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    try {
      splitter.setPointerCapture(e.pointerId);
    } catch { /* sự kiện synthetic không hỗ trợ capture */ }
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const move = (ev) => {
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplit(Math.min(75, Math.max(25, pct)));
    };
    const up = (ev) => {
      try {
        splitter.releasePointerCapture(ev.pointerId);
      } catch { /* bỏ qua */ }
      splitter.removeEventListener("pointermove", move);
      splitter.removeEventListener("pointerup", up);
      splitter.removeEventListener("pointercancel", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setSplit((v) => {
        saveSplit(v);
        return v;
      });
    };
    splitter.addEventListener("pointermove", move);
    splitter.addEventListener("pointerup", up);
    splitter.addEventListener("pointercancel", up);
  };

  // --- Chỉnh sửa kết quả ---
  const handleApplyGlyph = (recIdx, glyphIdx, ch) => {
    setResult((r) => (r ? applyGlyphEdit(r, recIdx, glyphIdx, ch) : r));
  };
  const handleLineEdit = (recIdx, patch) => {
    setResult((r) => (r ? applyLineEdit(r, recIdx, patch) : r));
    setSelected(null);
  };

  // --- Lưu / cập nhật tài liệu ---
  const handleSaveNewDoc = async (e) => {
    e.preventDefault();
    if (!result || !file || file.saved) return;
    setSavingDoc(true);
    try {
      const fd = new FormData();
      fd.append("title", saveTitle || file.name);
      fd.append("ocr_result_json", JSON.stringify(toPlainResult(result)));
      fd.append("original_image", file);
      if (result.ocr_image?.startsWith("data:")) {
        fd.append("ocr_image", await dataUrlToBlob(result.ocr_image), "ocr_result.jpg");
      } else {
        fd.append("ocr_image", file);
      }
      const j = await createDocument(apiBase, token, fd);
      setSaveModalOpen(false);
      setSelectedDocId(j.id);
      pushToast("success", "Đã lưu tài liệu", saveTitle || file.name);
      loadHistory();
    } catch (e2) {
      if (!handleUnauthorized(e2)) pushToast("error", "Không lưu được", e2.message);
    } finally {
      setSavingDoc(false);
    }
  };

  const handleUpdateDoc = async () => {
    if (!selectedDocId || !result) return;
    try {
      await updateDocument(apiBase, token, selectedDocId, {
        title: saveTitle || undefined,
        ocr_result: toPlainResult(result),
      });
      pushToast("success", "Đã cập nhật thay đổi");
      loadHistory();
    } catch (e) {
      if (!handleUnauthorized(e)) pushToast("error", "Cập nhật thất bại", e.message);
    }
  };

  // --- Suy diễn hiển thị ---
  const processedSrc = result?.ocr_image || preResult?.image;
  const displaySrc = view === "processed" && processedSrc ? processedSrc : imgUrl;
  const boxesEnabled = view === "processed" && !!result?.ocr_image;
  const stats = resultStats(result);
  const pm = preResult?.meta || result?.preprocess;
  const metaCaption = pm?.applied
    ? [pm.stage, pm.skew_angle != null && `góc ${pm.skew_angle}°`].filter(Boolean).join(" · ")
    : view === "original"
    ? "ảnh gốc"
    : null;
  const exportBaseName = saveTitle || file?.name || "ket-qua-ocr";
  const loading = phase != null;

  return (
    <div className="wrap">
      {/* inert khi chưa đăng nhập: loại nội dung sau màn khóa khỏi tab order,
          click và accessibility tree (không chỉ che mờ bằng CSS). */}
      <div inert={!token ? "" : undefined}>
      <Header
        activeTab={activeTab}
        onTab={setActiveTab}
        theme={theme}
        onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
        health={health}
        onOpenSettings={() => setSettingsOpen(true)}
        user={user}
        onOpenAuth={() => {
          setAuthMode("login");
          setAuthModalOpen(true);
        }}
        onLogout={handleLogout}
      />

      {activeTab === "history" && (
        <HistoryPanel
          docs={historyDocs}
          loading={historyLoading}
          selectedDocId={selectedDocId}
          onOpen={openDocument}
          onDelete={requestDeleteDoc}
        />
      )}

      {activeTab === "ocr" && (
        <>
          {/* THANH CÔNG CỤ CHÍNH */}
          <div className="toolbar">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                onPickFile(e.target.files?.[0] || null);
                e.target.value = "";
              }}
            />
            {file ? (
              <div className="file-chip">
                <span className="file-chip-dot" />
                <button
                  className="file-chip-name"
                  title="Chọn ảnh khác"
                  onClick={() => onPickFile(undefined, true)}
                >
                  {file.name}
                </button>
                <button className="file-chip-x" onClick={clearFile} aria-label="Bỏ ảnh">
                  ✕
                </button>
              </div>
            ) : (
              <button className="btn btn-ghost" onClick={() => onPickFile(undefined, true)}>
                ⊕ Chọn ảnh…
              </button>
            )}

            {params.preprocess && !file?.saved && (
              <button
                className="btn btn-ghost"
                onClick={runPreprocessOnly}
                disabled={!file || loading}
                title="Chỉ chạy tiền xử lý để xem trước ảnh"
              >
                Tiền xử lý
              </button>
            )}
            <button
              className="btn btn-primary"
              onClick={runOcr}
              disabled={!file || file.saved || loading}
            >
              {loading && phase !== "pre" ? <Spinner size={14} /> : "🔍"} Chạy OCR
            </button>

            <button
              className={`ai-toggle ${useAI ? "on" : ""}`}
              onClick={() => setUseAI(!useAI)}
              disabled={loading}
              title="Sau khi OCR, dùng SikuBERT sửa lỗi chính tả Hán–Nôm (chạy lâu hơn ~2 lần)"
              aria-pressed={useAI}
            >
              <span className="ai-switch" />
              Hiệu đính AI <span className="ai-tag">SikuBERT</span>
            </button>

            {token && result && (
              selectedDocId ? (
                <button className="btn btn-outline" onClick={handleUpdateDoc} disabled={loading}>
                  💾 Cập nhật
                </button>
              ) : (
                !file?.saved && (
                  <button
                    className="btn btn-outline"
                    onClick={() => {
                      setSaveTitle(file?.name?.replace(/\.[^.]+$/, "") || "");
                      setSaveModalOpen(true);
                    }}
                  >
                    📥 Lưu vào tài khoản
                  </button>
                )
              )
            )}

            <div className="toolbar-spacer" />
            {stats && (
              <span className="toolbar-stats">
                ⚡ {stats.nChars} chữ · {stats.nCols} cột
                {elapsedMs != null && ` · ${(elapsedMs / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>

          {/* THAM SỐ NÂNG CAO */}
          <details className="advanced">
            <summary>
              <span className="advanced-chev">▶</span> Tùy chỉnh tiền xử lý nâng cao
              <label
                className="chk-label advanced-enable"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  checked={params.preprocess}
                  onChange={(e) => setParam("preprocess", e.target.checked)}
                />
                Bật tiền xử lý
              </label>
            </summary>
            <div className={`params-grid ${params.preprocess ? "" : "disabled"}`}>
              <div className="field">
                <span className="field-label">Stage đầu vào OCR</span>
                <select value={params.stage} onChange={(e) => setParam("stage", e.target.value)}>
                  {serverOpts.stages.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Lật ảnh (flip)</span>
                <select value={params.flip} onChange={(e) => setParam("flip", e.target.value)}>
                  {serverOpts.flip_directions.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Khử nhiễu</span>
                <select
                  value={params.noise_method}
                  onChange={(e) => setParam("noise_method", e.target.value)}
                >
                  {serverOpts.noise_methods.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Chiều rộng resize</span>
                <input
                  type="number"
                  step="100"
                  value={params.resize_width}
                  onChange={(e) =>
                    setParam("resize_width", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <div className="field">
                <span className="field-label">Canny low</span>
                <input
                  type="number"
                  value={params.canny_low}
                  onChange={(e) =>
                    setParam("canny_low", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <div className="field">
                <span className="field-label">Canny high</span>
                <input
                  type="number"
                  value={params.canny_high}
                  onChange={(e) =>
                    setParam("canny_high", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <div className="field">
                <span className="field-label">Khử nghiêng (±°)</span>
                <input
                  type="number"
                  step="0.5"
                  value={params.deskew_range}
                  onChange={(e) =>
                    setParam("deskew_range", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <div className="field">
                <span className="field-label">CLAHE clip</span>
                <input
                  type="number"
                  step="0.5"
                  value={params.clahe_clip}
                  onChange={(e) =>
                    setParam("clahe_clip", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <div className="field">
                <span className="field-label">CLAHE tile</span>
                <input
                  type="number"
                  value={params.clahe_tile}
                  onChange={(e) =>
                    setParam("clahe_tile", e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
              <button className="btn btn-ghost" onClick={() => setParams(DEFAULT_PARAMS)}>
                Về mặc định
              </button>
              <p className="advanced-hint">
                🪵 <b>Vì sao mặc định lật ngang?</b> Ảnh chụp trực tiếp ván khắc có chữ ngược —
                lật ngang trả chữ về chiều đọc đúng. Nếu OCR bản in trên giấy, chọn flip{" "}
                <b>none</b>.
              </p>
            </div>
          </details>

          {error && <div className="error-banner">⚠️ {error}</div>}

          {/* KHÔNG GIAN LÀM VIỆC — kéo splitter giữa 2 panel để chỉnh tỷ lệ */}
          <div
            className="workspace"
            ref={workspaceRef}
            style={{ "--split": `${split}%` }}
          >
            <ViewerPanel
              displaySrc={displaySrc}
              results={result?.results}
              boxesEnabled={boxesEnabled}
              showBoxes={showBoxes}
              onToggleBoxes={() => setShowBoxes(!showBoxes)}
              hovered={hovered}
              onHover={setHovered}
              selected={selected}
              onSelect={setSelected}
              view={view}
              onView={setView}
              hasProcessed={!!processedSrc}
              metaCaption={metaCaption}
              phase={phase}
              onPickFile={onPickFile}
              aiApplied={!!result?.ai?.applied}
            />
            <div
              className="splitter"
              role="separator"
              aria-orientation="vertical"
              aria-label="Kéo để chỉnh kích thước hai bảng"
              aria-valuenow={Math.round(split)}
              aria-valuemin={25}
              aria-valuemax={75}
              tabIndex={0}
              title="Kéo để chỉnh kích thước · nhấp đúp để đặt lại"
              onPointerDown={onSplitterDown}
              onDoubleClick={resetSplit}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") {
                  e.preventDefault();
                  nudgeSplit(-2);
                } else if (e.key === "ArrowRight") {
                  e.preventDefault();
                  nudgeSplit(2);
                }
              }}
            />
            <ProofPanel
              result={result}
              resultView={resultView}
              setResultView={setResultView}
              aiView={aiView}
              setAiView={setAiView}
              hovered={hovered}
              setHovered={setHovered}
              selected={selected}
              setSelected={setSelected}
              onApplyGlyph={handleApplyGlyph}
              onLineEdit={handleLineEdit}
              exportBaseName={exportBaseName}
              onToast={pushToast}
            />
          </div>
        </>
      )}
      </div>

      {/* MODALS */}
      {settingsOpen && (
        <SettingsModal
          apiBase={apiBase}
          health={health}
          checking={health === "checking"}
          onChangeApiBase={changeApiBase}
          onCheck={(base) => checkHealth(base)}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {authModalOpen && (
        <AuthModal
          mode={authMode}
          onSwitchMode={(m) => {
            setAuthMode(m);
            setAuthError(null);
          }}
          error={authError}
          onSubmit={handleAuthSubmit}
          onGoogleCredential={handleGoogleCredential}
          onClose={() => setAuthModalOpen(false)}
        />
      )}

      {saveModalOpen && (
        <Modal title="Lưu kết quả OCR" onClose={() => setSaveModalOpen(false)}>
          <form className="modal-form" onSubmit={handleSaveNewDoc}>
            <div className="form-group">
              <label htmlFor="save-title">Tiêu đề tài liệu</label>
              <input
                id="save-title"
                type="text"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                required
                placeholder="Ví dụ: Ván khắc trang 3"
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setSaveModalOpen(false)}
              >
                Hủy
              </button>
              <button type="submit" className="btn btn-primary" disabled={savingDoc}>
                {savingDoc ? "Đang lưu…" : "Lưu vào máy chủ"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      <ConfirmDialog
        open={!!confirmState}
        title={confirmState?.title}
        message={confirmState?.message}
        onConfirm={confirmState?.onConfirm}
        onCancel={() => setConfirmState(null)}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />

      {/* MÀN KHÓA KHI CHƯA ĐĂNG NHẬP */}
      {!token && (
        <div className="lock-overlay">
          <div className="lock-card">
            <div className="seal-logo lock-logo">木</div>
            <h2 className="lock-title">Mộc Bản OCR</h2>
            <span className="lock-subtitle">Hệ thống số hóa di sản chữ Hán–Nôm</span>
            <p className="lock-text">
              Vui lòng{" "}
              <button
                className="link-btn"
                autoFocus
                onClick={() => {
                  setAuthMode("login");
                  setAuthModalOpen(true);
                }}
              >
                đăng nhập
              </button>{" "}
              hoặc{" "}
              <button
                className="link-btn"
                onClick={() => {
                  setAuthMode("register");
                  setAuthModalOpen(true);
                }}
              >
                đăng ký
              </button>{" "}
              để sử dụng dịch vụ.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
