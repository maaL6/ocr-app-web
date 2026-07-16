import { useEffect, useRef, useState } from "react";

const DEFAULT_API = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const FALLBACK_OPTS = {
  stages: ["warped", "deskewed", "clahe", "denoised", "flipped", "inverted"],
  noise_methods: ["gaussian", "median", "bilateral", "nlm"],
  flip_directions: ["horizontal", "vertical", "both", "none"],
};

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

export default function App() {
  // --- States ---
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [serverOpts, setServerOpts] = useState(FALLBACK_OPTS);
  const [params, setParams] = useState(DEFAULT_PARAMS);

  const [file, setFile] = useState(null);
  const [imgUrl, setImgUrl] = useState(null); // ảnh gốc hiển thị
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // { results, columns, full_text, ocr_image, preprocess }
  const [preResult, setPreResult] = useState(null); // { image, meta } từ /preprocess
  const [hovered, setHovered] = useState(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [view, setView] = useState("processed"); // "processed" | "original"
  const [resultView, setResultView] = useState("columns"); // "columns" | "list"
  const [imgVersion, setImgVersion] = useState(0);

  // --- Auth states ---
  const [token, setToken] = useState(localStorage.getItem("token") || null);
  const [user, setUser] = useState(localStorage.getItem("user") ? JSON.parse(localStorage.getItem("user")) : null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login"); // "login" | "register"
  const [authForm, setAuthForm] = useState({ email: "", password: "", fullname: "", phone_number: "" });
  const [authError, setAuthError] = useState(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // --- Tabs ---
  const [activeTab, setActiveTab] = useState("ocr"); // "ocr" | "history" | "changelog"

  // --- History/Documents states ---
  const [historyDocs, setHistoryDocs] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [saveDocModalOpen, setSaveDocModalOpen] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");
  const [savingDoc, setSavingDoc] = useState(false);

  // --- Inline Editing states ---
  const [editingIndex, setEditingIndex] = useState(null);
  const [editText, setEditText] = useState("");
  const [editCol, setEditCol] = useState(1);

  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  // Đổi tham số -> reset kết quả tiền xử lý cũ
  const setParam = (k, v) => {
    setParams((p) => ({ ...p, [k]: v }));
    setPreResult(null);
  };

  // --- Authenticated Image Fetcher ---
  // Gọi API lấy ảnh gốc hoặc ảnh OCR có truyền header Authorization
  async function fetchAuthenticatedImage(imagePath) {
    try {
      const url = `${apiBase}${imagePath}`;
      const headers = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const r = await fetch(url, { headers });
      if (!r.ok) throw new Error("Không thể tải ảnh");
      const blob = await r.blob();
      return URL.createObjectURL(blob);
    } catch (e) {
      console.error(e);
      return null;
    }
  }

  // --- Health + options ---
  async function checkHealth() {
    setHealth("checking");
    try {
      const r = await fetch(`${apiBase}/health`);
      const j = await r.json();
      setHealth(j.status === "ok" ? "ok" : "down");
    } catch {
      setHealth("down");
    }
  }

  async function loadOptions() {
    try {
      const r = await fetch(`${apiBase}/options`);
      if (r.ok) setServerOpts(await r.json());
    } catch {
      /* dùng fallback */
    }
  }

  useEffect(() => {
    checkHealth();
    loadOptions();
    if (token) {
      loadHistory();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // --- Chọn file ---
  function onPick(f) {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      setError("File phải là ảnh");
      return;
    }
    setError(null);
    setResult(null);
    setPreResult(null);
    setSelectedDocId(null);
    setFile(f);
    if (imgUrl) URL.revokeObjectURL(imgUrl);
    setImgUrl(URL.createObjectURL(f));
    setView("original");
  }

  // Gửi kèm tham số tiền xử lý
  function appendPreParams(fd) {
    const { preprocess, ...rest } = params;
    Object.entries(rest).forEach(([k, v]) => fd.append(k, String(v)));
  }

  // --- Chỉ chạy tiền xử lý ---
  async function runPreprocess() {
    if (!file) return null;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      appendPreParams(fd);
      const r = await fetch(`${apiBase}/preprocess`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const j = await r.json();
      const pre = { image: j.image, meta: j.preprocess };
      setPreResult(pre);
      setView("processed");
      return pre;
    } catch (e) {
      setError(e.message || String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }

  // --- Chạy OCR ---
  async function runOcr() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setEditingIndex(null);
    const t0 = performance.now();
    try {
      const fd = new FormData();
      if (params.preprocess) {
        let pre = preResult;
        if (!pre) {
          setLoading(false);
          pre = await runPreprocess();
          setLoading(true);
          if (!pre) return;
        }
        const blob = await (await fetch(pre.image)).blob();
        fd.append("file", blob, "preprocessed.jpg");
        fd.append("preprocess", "false");
      } else {
        fd.append("file", file);
        fd.append("preprocess", "false");
      }
      const r = await fetch(`${apiBase}/ocr`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const j = await r.json();
      j._ms = Math.round(performance.now() - t0);
      setResult(j);
      setView(params.preprocess ? "processed" : "original");
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  // --- Vẽ ảnh + Bounding Boxes lên Canvas ---
  const processedSrc = result?.ocr_image || preResult?.image;
  const displaySrc = view === "processed" && processedSrc ? processedSrc : imgUrl;
  const boxesOnThisView = view === "processed" && !!result?.ocr_image;

  useEffect(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);

    if (!showBoxes || !boxesOnThisView || !result?.results) return;
    result.results.forEach((item, i) => {
      const poly = item.bbox;
      if (!poly || !poly.length) return;
      const active = hovered === i;
      ctx.beginPath();
      poly.forEach(([x, y], k) => (k === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.closePath();
      ctx.lineWidth = active ? 4 : 2;
      ctx.strokeStyle = active ? "#ff3b30" : "#801c1c";
      ctx.fillStyle = active ? "rgba(255, 59, 48, 0.18)" : "rgba(128, 28, 28, 0.1)";
      ctx.fill();
      ctx.stroke();
    });
  }, [imgVersion, result, hovered, showBoxes, boxesOnThisView, displaySrc]);

  // --- Logic Auth (Đăng nhập / Đăng ký) ---
  const toggleAuthMode = () => {
    setAuthMode(authMode === "login" ? "register" : "login");
    setAuthError(null);
  };

  const handleAuthInputChange = (e) => {
    setAuthForm({ ...authForm, [e.target.name]: e.target.value });
  };

  async function handleAuthSubmit(e) {
    e.preventDefault();
    setAuthError(null);
    try {
      if (authMode === "login") {
        const r = await fetch(`${apiBase}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: authForm.email, password: authForm.password }),
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || "Đăng nhập thất bại");
        
        localStorage.setItem("token", j.access_token);
        localStorage.setItem("user", JSON.stringify(j.user));
        setToken(j.access_token);
        setUser(j.user);
        setAuthModalOpen(false);
        setAuthForm({ email: "", password: "", fullname: "", phone_number: "" });
      } else {
        const r = await fetch(`${apiBase}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(authForm),
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || "Đăng ký thất bại");
        alert("Đăng ký thành công! Hãy đăng nhập bằng tài khoản mới.");
        setAuthMode("login");
      }
    } catch (err) {
      setAuthError(err.message || String(err));
    }
  }

  // --- Google Sign-In Callback ---
  async function handleGoogleLogin(response) {
    setAuthError(null);
    try {
      const r = await fetch(`${apiBase}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: response.credential }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "Đăng nhập Google thất bại");

      localStorage.setItem("token", j.access_token);
      localStorage.setItem("user", JSON.stringify(j.user));
      setToken(j.access_token);
      setUser(j.user);
      setAuthModalOpen(false);
      setUserMenuOpen(false);
      setAuthForm({ email: "", password: "", fullname: "", phone_number: "" });
    } catch (err) {
      setAuthError(err.message || String(err));
    }
  }

  // Khởi tạo nút Đăng nhập Google
  useEffect(() => {
    if (authModalOpen && window.google) {
      try {
        window.google.accounts.id.initialize({
          client_id: "316323533715-u77bsr5qbo7p6b42g161cvcvlojfqbm9.apps.googleusercontent.com",
          callback: handleGoogleLogin,
        });
        window.google.accounts.id.renderButton(
          document.getElementById("googleBtn"),
          { theme: "outline", size: "large", width: 372 }
        );
      } catch (e) {
        console.error("Lỗi Google Init:", e);
      }
    }
  }, [authModalOpen]);

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    setHistoryDocs([]);
    setSelectedDocId(null);
    setUserMenuOpen(false);
  }

  // --- Logic quản lý Lịch sử (Documents) ---
  async function loadHistory() {
    if (!token) return;
    setHistoryLoading(true);
    try {
      const r = await fetch(`${apiBase}/documents`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (r.status === 401) {
        handleLogout();
        return;
      }
      if (r.ok) {
        setHistoryDocs(await r.json());
      }
    } catch (e) {
      console.error("Lỗi lấy lịch sử:", e);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadDocDetails(docId) {
    if (!token) return;
    setLoading(true);
    setError(null);
    setEditingIndex(null);
    try {
      const r = await fetch(`${apiBase}/documents/${docId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!r.ok) throw new Error("Không thể tải tài liệu chi tiết");
      const doc = await r.json();

      setSelectedDocId(doc.id);
      setSaveTitle(doc.title || "");
      
      // Tải ảnh nguyên bản qua authenticated endpoint
      const originalUrl = await fetchAuthenticatedImage(doc.original_image_url);
      setImgUrl(originalUrl);
      setFile({ name: doc.title || "Tài liệu lưu trữ" }); // Giả lập file

      // Nạp OCR result
      const ocrRes = doc.ocr_result;
      
      // Tải ảnh OCR qua authenticated endpoint nếu có
      if (doc.ocr_image_url) {
        const ocrUrl = await fetchAuthenticatedImage(doc.ocr_image_url);
        ocrRes.ocr_image = ocrUrl;
      }
      
      setResult(ocrRes);
      setPreResult(null);
      setView("processed");
      setActiveTab("ocr");
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  // Chuyển base64 DataURL thành Blob
  async function dataURLtoBlob(dataurl) {
    const res = await fetch(dataurl);
    return await res.blob();
  }

  // Lưu mới tài liệu lên server
  async function handleSaveNewDoc(e) {
    e.preventDefault();
    if (!result || !file) return;
    setSavingDoc(true);
    try {
      const fd = new FormData();
      fd.append("title", saveTitle || file.name);
      
      // Tạo một bản clone kết quả OCR để lưu (xóa ocr_image base64 cho đỡ nặng DB nếu backend lưu ảnh riêng)
      const cleanOcrResult = {
        results: result.results,
        columns: result.columns,
        full_text: result.full_text,
        preprocess: result.preprocess || { applied: false }
      };
      fd.append("ocr_result_json", JSON.stringify(cleanOcrResult));

      // Append ảnh gốc
      fd.append("original_image", file);

      // Chuyển ảnh OCR dạng base64 thành Blob
      if (result.ocr_image && result.ocr_image.startsWith("data:")) {
        const ocrBlob = await dataURLtoBlob(result.ocr_image);
        fd.append("ocr_image", ocrBlob, "ocr_result.jpg");
      } else {
        // Fallback gửi ảnh gốc nếu không có ảnh OCR
        fd.append("ocr_image", file);
      }

      const r = await fetch(`${apiBase}/documents`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: fd
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "Không thể lưu tài liệu");

      alert("Lưu tài liệu thành công!");
      setSaveDocModalOpen(false);
      loadHistory();
      setSelectedDocId(j.id);
    } catch (err) {
      alert("Lỗi: " + err.message);
    } finally {
      setSavingDoc(false);
    }
  }

  // Cập nhật tài liệu cũ đã sửa đổi
  async function handleUpdateDoc() {
    if (!selectedDocId || !result) return;
    setLoading(true);
    try {
      const cleanOcrResult = {
        results: result.results,
        columns: result.columns,
        full_text: result.full_text,
        preprocess: result.preprocess || { applied: false }
      };

      const r = await fetch(`${apiBase}/documents/${selectedDocId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          title: saveTitle || undefined,
          ocr_result: cleanOcrResult
        })
      });
      if (!r.ok) throw new Error("Cập nhật thất bại");
      alert("Đã cập nhật các thay đổi lên máy chủ!");
      loadHistory();
    } catch (err) {
      alert("Lỗi: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  // Xóa tài liệu khỏi lịch sử
  async function handleDeleteDoc(e, docId) {
    e.stopPropagation();
    if (!confirm("Bạn có chắc chắn muốn xóa tài liệu này?")) return;
    try {
      const r = await fetch(`${apiBase}/documents/${docId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!r.ok) throw new Error("Không thể xóa tài liệu");
      
      if (selectedDocId === docId) {
        setSelectedDocId(null);
        setResult(null);
        setFile(null);
        setImgUrl(null);
      }
      loadHistory();
    } catch (e) {
      alert("Lỗi: " + e.message);
    }
  }

  // --- Logic Chỉnh sửa kết quả OCR trực tiếp ---
  const handleStartEdit = (idx) => {
    if (!result?.results?.[idx]) return;
    const rec = result.results[idx];
    setEditingIndex(idx);
    setEditText(rec.text);
    setEditCol(rec.column || 1);
  };

  const handleSaveInlineEdit = () => {
    if (editingIndex === null || !result) return;
    
    // Copy results array
    const newResults = [...result.results];
    newResults[editingIndex] = {
      ...newResults[editingIndex],
      text: editText,
      column: Number(editCol)
    };

    // Rebuild columns và full_text
    const colsMap = {};
    newResults.forEach(r => {
      const c = r.column || 1;
      (colsMap[c] ||= []).push(r);
    });

    const sortedColIndices = Object.keys(colsMap).map(Number).sort((a, b) => a - b);
    const updatedColumns = sortedColIndices.map(cIdx => {
      const colSegments = colsMap[cIdx];
      return {
        index: cIdx,
        text: colSegments.map(r => r.text).join(""),
        avg_score: colSegments.length ? (colSegments.reduce((sum, r) => sum + (r.confidence || 0), 0) / colSegments.length) : 1.0
      };
    });

    const updatedFullText = updatedColumns.map(c => c.text).join("\n");

    setResult({
      ...result,
      results: newResults,
      columns: updatedColumns,
      full_text: updatedFullText
    });

    setEditingIndex(null);
  };

  // Gom nhóm kết quả để hiển thị theo dạng cột dọc
  const recordsByColumn = {};
  (result?.results || []).forEach((rec, idx) => {
    (recordsByColumn[rec.column] ||= []).push({ rec, idx });
  });

  const pm = preResult?.meta || result?.preprocess;
  const healthColor = health === "ok" ? "#2e7d32" : health === "checking" ? "#ef6c00" : "#c62828";

  return (
    <div className="wrap">
      {/* HEADER */}
      <header>
        <a href="/" className="brand" onClick={(e) => { e.preventDefault(); setActiveTab("ocr"); }}>
          <div className="logo-box">木</div>
          <div className="brand-text">
            <h1 className="brand-title">Mộc Bản</h1>
            <span className="brand-subtitle">Di sản số · Tri thức châu Á</span>
          </div>
        </a>

        {/* Thanh Điều Hướng Menu */}
        <ul className="nav-links">
          <li>
            <a href="#ocr" className={activeTab === "ocr" ? "active" : ""} 
              onClick={(e) => { e.preventDefault(); setActiveTab("ocr"); }}>
              Phần mềm OCR
            </a>
          </li>
          {token && (
            <li>
              <a href="#history" className={activeTab === "history" ? "active" : ""}
                onClick={(e) => { e.preventDefault(); setActiveTab("history"); }}>
                Lịch sử quét
              </a>
            </li>
          )}
        </ul>

        {/* Khối Actions (API + User) */}
        <div className="header-actions">
          <div className="api-widget">
            <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} spellCheck={false} placeholder="URL server API" />
            <button onClick={() => { checkHealth(); loadOptions(); }}>Check</button>
            <span className="health-dot" style={{ backgroundColor: healthColor, color: healthColor }} />
          </div>

          <div className="lang-switcher">
            <button className="lang-btn active">VI</button>
            <button className="lang-btn">EN</button>
          </div>

          {user ? (
            <div className="user-menu">
              <button className="user-btn" onClick={() => setUserMenuOpen(!userMenuOpen)}>
                <div className="user-avatar">{user.fullname?.charAt(0).toUpperCase() || "U"}</div>
                <span>{user.fullname?.split(" ").pop() || "Tài khoản"}</span>
                <span>▼</span>
              </button>
              {userMenuOpen && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-dropdown-name">{user.fullname}</div>
                    <div className="user-dropdown-email">{user.email}</div>
                  </div>
                  <button className="user-dropdown-item" onClick={() => { setActiveTab("history"); setUserMenuOpen(false); }}>
                    🕰️ Lịch sử quét
                  </button>
                  <button className="user-dropdown-item logout" onClick={handleLogout}>
                    🔑 Đăng xuất
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button className="btn btn-primary" onClick={() => { setAuthMode("login"); setAuthModalOpen(true); }}>
              👤 Đăng nhập
            </button>
          )}
        </div>
      </header>

      {/* CHUYỂN TABS CHÍNH */}
      {activeTab === "history" && (
        <div className="card">
          <h2 className="card-title">🕰️ Lịch sử quét tài liệu của bạn</h2>
          {historyLoading ? (
            <div className="loading-indicator"><div className="spinner" /> Đang tải lịch sử...</div>
          ) : historyDocs.length === 0 ? (
            <p className="muted" style={{ textAlign: "center", padding: "40px 0" }}>
              Tài khoản của bạn chưa lưu trữ tài liệu quét nào. Hãy chạy OCR ở tab "Phần mềm OCR" và chọn "Lưu vào tài khoản".
            </p>
          ) : (
            <div className="list-group">
              {historyDocs.map((doc) => (
                <div key={doc.id} className={`list-group-item ${selectedDocId === doc.id ? "list-group-item-active" : ""}`}
                  onClick={() => loadDocDetails(doc.id)}>
                  <div className="item-info">
                    <span className="item-title">{doc.title || `Tài liệu #${doc.id}`}</span>
                    <span className="item-snippet">{doc.full_text || "(Trống)"}</span>
                    <span className="item-meta">
                      Quét lúc: {new Date(doc.created_at).toLocaleString("vi-VN")}
                    </span>
                  </div>
                  <div className="item-actions">
                    <button className="icon-btn-delete" title="Xóa tài liệu"
                      onClick={(e) => handleDeleteDoc(e, doc.id)}>
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "ocr" && (
        <>
          {/* KHU VỰC TẢI ẢNH */}
          <div className="card">
            <div className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); onPick(e.dataTransfer.files?.[0]); }}
              onClick={() => document.getElementById("fileInput").click()}>
              <input id="fileInput" type="file" accept="image/*" hidden onChange={(e) => onPick(e.target.files?.[0])} />
              <div className="dropzone-icon">🪵</div>
              {file ? (
                <span className="dropzone-text">📄 {file.name}</span>
              ) : (
                <>
                  <span className="dropzone-text">Kéo-thả ảnh ván khắc mộc bản vào đây</span>
                  <span className="dropzone-sub">Hoặc nhấn vào đây để chọn tệp hình ảnh</span>
                </>
              )}
            </div>
          </div>

          {/* BẢNG ĐIỀU KHIỂN TIỀN XỬ LÝ */}
          <fieldset className="params-fieldset">
            <legend className="params-legend">
              <label className="chk-label">
                <input type="checkbox" checked={params.preprocess} onChange={(e) => setParam("preprocess", e.target.checked)} />
                Kích hoạt Tiền xử lý ván khắc mộc bản
              </label>
            </legend>
            <div className={`params-grid ${params.preprocess ? "" : "disabled"}`}>
              <div className="field">
                <span className="field-label">Stage đầu vào OCR</span>
                <select value={params.stage} onChange={(e) => setParam("stage", e.target.value)}>
                  {serverOpts.stages.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Lật ảnh (Flip)</span>
                <select value={params.flip} onChange={(e) => setParam("flip", e.target.value)}>
                  {serverOpts.flip_directions.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Phương pháp khử nhiễu</span>
                <select value={params.noise_method} onChange={(e) => setParam("noise_method", e.target.value)}>
                  {serverOpts.noise_methods.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="field">
                <span className="field-label">Chiều rộng ảnh (Resize)</span>
                <input type="number" step="100" value={params.resize_width}
                  onChange={(e) => setParam("resize_width", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="field">
                <span className="field-label">Canny Low</span>
                <input type="number" value={params.canny_low}
                  onChange={(e) => setParam("canny_low", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="field">
                <span className="field-label">Canny High</span>
                <input type="number" value={params.canny_high}
                  onChange={(e) => setParam("canny_high", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="field">
                <span className="field-label">Khoảng khử nghiêng°</span>
                <input type="number" step="0.5" value={params.deskew_range}
                  onChange={(e) => setParam("deskew_range", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="field">
                <span className="field-label">CLAHE Clip Limit</span>
                <input type="number" step="0.5" value={params.clahe_clip}
                  onChange={(e) => setParam("clahe_clip", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="field">
                <span className="field-label">CLAHE Tile Size</span>
                <input type="number" value={params.clahe_tile}
                  onChange={(e) => setParam("clahe_tile", e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <button className="btn btn-reset" onClick={() => setParams(DEFAULT_PARAMS)}>Mặc định</button>
            </div>
          </fieldset>

          {/* HÀNG NÚT ĐIỀU KHIỂN CHÍNH */}
          <div className="actions-row">
            <div className="actions-left">
              <button className="btn btn-secondary" onClick={runPreprocess} disabled={!file || loading || !params.preprocess}>
                ⚙️ {loading ? "Đang xử lý..." : "Chạy tiền xử lý"}
              </button>
              <button className="btn btn-primary" onClick={runOcr} disabled={!file || loading}>
                🔍 {loading ? "Đang nhận dạng..." : "Chạy OCR Mộc Bản"}
              </button>

              {token && result && (
                selectedDocId ? (
                  <button className="btn btn-outline-accent" onClick={handleUpdateDoc} disabled={loading}>
                    💾 Cập nhật thay đổi
                  </button>
                ) : (
                  <button className="btn btn-outline-accent" onClick={() => { setSaveTitle(file?.name || ""); setSaveDocModalOpen(true); }}>
                    📥 Lưu vào tài khoản
                  </button>
                )
              )}

              <label className="chk-label" style={{ marginLeft: "10px" }}>
                <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
                Hiện bounding box
              </label>
            </div>

            <div className="actions-right">
              {processedSrc && (
                <div className="segmented-control">
                  <button className={view === "processed" ? "active" : ""} onClick={() => setView("processed")}>Ảnh đã xử lý</button>
                  <button className={view === "original" ? "active" : ""} onClick={() => setView("original")}>Ảnh gốc</button>
                </div>
              )}
              {result && (
                <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-secondary)" }}>
                  ⚡ {result.results?.length || 0} dòng · {result._ms} ms
                </span>
              )}
            </div>
          </div>

          {/* THÔNG TIN TIỀN XỬ LÝ (META) */}
          {pm && (
            <div className="preprocess-meta">
              {pm.applied ? (
                <>
                  Phương pháp: <b>{pm.stage}</b> · Khử nghiêng: <b>{pm.auto_detected ? pm.strategy : "Không"}</b> · Góc xoay: <b>{pm.skew_angle}°</b> · Kích thước: <b>{pm.input_shape}</b> → <b>{pm.output_shape}</b>
                </>
              ) : <>Tiền xử lý ảnh: <b>Tắt</b></>}
            </div>
          )}

          {/* LỖI HỆ THỐNG */}
          {error && <div className="error-banner">⚠️ Lỗi: {error}</div>}

          {/* APP GRID: CANVAS TRÁI - KẾT QUẢ PHẢI */}
          <div className="app-grid">
            <div className="canvas-wrapper">
              {displaySrc ? (
                <>
                  <img ref={imgRef} src={displaySrc} alt="" style={{ display: "none" }} onLoad={() => setImgVersion((v) => v + 1)} />
                  <canvas ref={canvasRef} />
                </>
              ) : (
                <div className="canvas-placeholder">
                  <div className="canvas-placeholder-icon">🪵</div>
                  <span>Chưa tải ảnh lên. Hãy chọn ảnh ở khu vực phía trên để bắt đầu.</span>
                </div>
              )}
            </div>

            <div className="card" style={{ minHeight: "350px" }}>
              <div className="panel-tab-bar">
                <h3>Kết quả {result?.columns?.length ? `(${result.columns.length} cột)` : ""}</h3>
                {result?.results?.length > 0 && (
                  <div className="segmented-control">
                    <button className={resultView === "columns" ? "active" : ""} onClick={() => setResultView("columns")}>Theo cột</button>
                    <button className={resultView === "list" ? "active" : ""} onClick={() => setResultView("list")}>Danh sách</button>
                  </div>
                )}
              </div>

              {/* EDITOR TRỰC TIẾP (Nếu có chọn dòng) */}
              {editingIndex !== null && result && (
                <div className="inline-editor">
                  <div className="inline-editor-header">Chỉnh sửa dòng #{editingIndex + 1}</div>
                  <div className="inline-editor-input-group">
                    <input type="text" value={editText} onChange={(e) => setEditText(e.target.value)} placeholder="Nhập chữ Hán-Nôm đã sửa..." autoFocus />
                    <input type="number" value={editCol} onChange={(e) => setEditCol(e.target.value)} title="Số cột" placeholder="Cột" />
                  </div>
                  <div className="ocr-edit-actions">
                    <button className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "11px" }} onClick={() => setEditingIndex(null)}>Hủy</button>
                    <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: "11px" }} onClick={handleSaveInlineEdit}>Lưu dòng</button>
                  </div>
                </div>
              )}

              {/* KHÔNG CÓ KẾT QUẢ */}
              {!result?.results?.length ? (
                <p className="muted" style={{ textAlign: "center", paddingTop: "50px" }}>Chưa có dữ liệu nhận dạng OCR.</p>
              ) : resultView === "columns" ? (
                /* HIỂN THỊ DẠNG CỘT DỌC TRUYỀN THỐNG (PHẢI QUA TRÁI) */
                <div className="ocr-columns">
                  {result.columns.map((col) => (
                    <div className="ocr-col" key={col.index}>
                      <div className="ocr-col-header">{col.index}</div>
                      <div className="ocr-col-body">
                        {recordsByColumn[col.index]?.map(({ rec, idx }) => (
                          <span key={idx} 
                            className={`ocr-col-text-span ${hovered === idx ? "hl" : ""}`}
                            title={`Độ tin cậy: ${(rec.confidence * 100).toFixed(1)}% | Click để sửa`}
                            onMouseEnter={() => setHovered(idx)} 
                            onMouseLeave={() => setHovered(null)}
                            onClick={() => handleStartEdit(idx)}>
                            {rec.text}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                /* HIỂN THỊ DẠNG DANH SÁCH HÀNG NGANG */
                <ul className="ocr-list">
                  {result.results.map((it, i) => (
                    <li key={i} className={`ocr-list-item ${hovered === i ? "hl" : ""}`}
                      onMouseEnter={() => setHovered(i)} 
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => handleStartEdit(i)}>
                      <span className="ocr-list-col-badge">Cột {it.column}</span>
                      <span className="ocr-list-text">{it.text}</span>
                      {it.confidence != null && (
                        <span className="ocr-list-confidence">{(it.confidence * 100).toFixed(1)}%</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {/* PHẦN TOÀN VĂN FULL TEXT */}
              {result?.full_text && (
                <div className="fulltext-section">
                  <div className="fulltext-header">
                    <span>TOÀN VĂN VĂN BẢN (FULL TEXT)</span>
                    <button className="btn btn-secondary" style={{ padding: "2px 8px", fontSize: "11px" }}
                      onClick={() => navigator.clipboard.writeText(result.full_text)}>
                      Copy
                    </button>
                  </div>
                  <pre className="fulltext-box">{result.full_text}</pre>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* MODAL ĐĂNG NHẬP / ĐĂNG KÝ */}
      {authModalOpen && (
        <div className="modal-overlay" onClick={() => setAuthModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{authMode === "login" ? "🔑 Đăng nhập" : "👤 Tạo tài khoản"}</h3>
              <button className="modal-close" onClick={() => setAuthModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              {authError && <div className="error-banner" style={{ marginBottom: "14px" }}>{authError}</div>}
              <form className="modal-form" onSubmit={handleAuthSubmit}>
                {authMode === "register" && (
                  <>
                    <div className="form-group">
                      <label>Họ và tên</label>
                      <input type="text" name="fullname" value={authForm.fullname} onChange={handleAuthInputChange} required placeholder="Ví dụ: Nguyễn Văn A" />
                    </div>
                    <div className="form-group">
                      <label>Số điện thoại</label>
                      <input type="tel" name="phone_number" value={authForm.phone_number} onChange={handleAuthInputChange} placeholder="Nhập số điện thoại..." />
                    </div>
                  </>
                )}
                <div className="form-group">
                  <label>Địa chỉ Email</label>
                  <input type="email" name="email" value={authForm.email} onChange={handleAuthInputChange} required placeholder="username@example.com" />
                </div>
                <div className="form-group">
                  <label>Mật khẩu</label>
                  <input type="password" name="password" value={authForm.password} onChange={handleAuthInputChange} required placeholder="••••••••" />
                </div>
                <button type="submit" className="btn btn-primary" style={{ width: "100%", padding: "11px", marginTop: "10px" }}>
                  {authMode === "login" ? "Đăng nhập ngay" : "Đăng ký tài khoản"}
                </button>
              </form>

              {authMode === "login" && (
                <>
                  <div style={{ textAlign: "center", margin: "16px 0 12px", color: "var(--text-muted)", fontSize: "11px", position: "relative" }}>
                    <span style={{ backgroundColor: "var(--card-bg)", padding: "0 10px", position: "relative", zIndex: 1 }}>Hoặc đăng nhập bằng</span>
                    <hr style={{ position: "absolute", top: "50%", left: 0, right: 0, margin: 0, border: "none", borderTop: "1px solid var(--border-color)" }} />
                  </div>
                  <div id="googleBtn" style={{ display: "flex", justifyContent: "center", minHeight: "40px" }}></div>
                </>
              )}

              <div className="modal-footer-text">
                {authMode === "login" ? (
                  <>Chưa có tài khoản? <span onClick={toggleAuthMode}>Đăng ký ngay</span></>
                ) : (
                  <>Đã có tài khoản? <span onClick={toggleAuthMode}>Đăng nhập</span></>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL LƯU TÀI LIỆU */}
      {saveDocModalOpen && (
        <div className="modal-overlay" onClick={() => setSaveDocModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">📥 Lưu kết quả OCR</h3>
              <button className="modal-close" onClick={() => setSaveDocModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <form className="modal-form" onSubmit={handleSaveNewDoc}>
                <div className="form-group">
                  <label>Tiêu đề tài liệu</label>
                  <input type="text" value={saveTitle} onChange={(e) => setSaveTitle(e.target.value)} required placeholder="Ví dụ: Ván khắc trang 3..." />
                </div>
                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "10px" }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setSaveDocModalOpen(false)}>Hủy</button>
                  <button type="submit" className="btn btn-primary" disabled={savingDoc}>
                    {savingDoc ? "Đang lưu..." : "Lưu vào máy chủ"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* LOCK OVERLAY CHO USER CHƯA ĐĂNG NHẬP */}
      {!token && (
        <div className="lock-overlay">
          <div className="lock-card">
            <a href="https://mocban.org" className="lock-brand-link" title="Quay lại trang chủ mocban.org">
              <div className="lock-logo">木</div>
              <h2 className="lock-title">Mộc Bản OCR</h2>
            </a>
            <span className="lock-subtitle">Hệ thống Số hóa Di sản chữ Hán-Nôm</span>
            <p className="lock-text">
              Chào mừng bạn đến với hệ thống số hóa và nhận diện ký tự Mộc Bản.
              Vui lòng <span className="lock-link" onClick={() => { setAuthMode("login"); setAuthModalOpen(true); }}>Đăng nhập</span> hoặc <span className="lock-link" onClick={() => { setAuthMode("register"); setAuthModalOpen(true); }}>Đăng ký</span> để sử dụng dịch vụ.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
