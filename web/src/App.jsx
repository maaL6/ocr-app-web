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
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [serverOpts, setServerOpts] = useState(FALLBACK_OPTS);
  const [params, setParams] = useState(DEFAULT_PARAMS);

  const [file, setFile] = useState(null);
  const [imgUrl, setImgUrl] = useState(null); // ảnh gốc (object URL)
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // { results, full_text, ocr_image, preprocess }
  const [preResult, setPreResult] = useState(null); // { image, meta } từ /preprocess
  const [hovered, setHovered] = useState(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [view, setView] = useState("processed"); // "processed" | "original"
  const [resultView, setResultView] = useState("columns"); // "columns" | "list"
  const [imgVersion, setImgVersion] = useState(0);

  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  // Đổi tham số -> kết quả tiền xử lý cũ không còn đúng nữa.
  const setParam = (k, v) => {
    setParams((p) => ({ ...p, [k]: v }));
    setPreResult(null);
  };

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    setFile(f);
    if (imgUrl) URL.revokeObjectURL(imgUrl);
    setImgUrl(URL.createObjectURL(f));
    setView("original");
  }

  // Các field tiền xử lý gửi kèm (không gồm cờ preprocess).
  function appendPreParams(fd) {
    const { preprocess, ...rest } = params;
    Object.entries(rest).forEach(([k, v]) => fd.append(k, String(v)));
  }

  // --- Chỉ chạy tiền xử lý để quan sát (không OCR) ---
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

  // --- Gọi OCR: dùng KẾT QUẢ tiền xử lý làm đầu vào ---
  async function runOcr() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const t0 = performance.now();
    try {
      const fd = new FormData();
      if (params.preprocess) {
        // Lấy ảnh đã tiền xử lý (chạy lại nếu chưa có / vừa đổi tham số),
        // rồi OCR chính ảnh đó với preprocess=false.
        let pre = preResult;
        if (!pre) {
          setLoading(false); // runPreprocess tự set lại
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

  // Ảnh đã xử lý: ưu tiên ảnh từ OCR (có bbox), nếu chưa OCR thì lấy ảnh
  // từ bước /preprocess để quan sát.
  const processedSrc = result?.ocr_image || preResult?.image;
  const displaySrc = view === "processed" && processedSrc ? processedSrc : imgUrl;
  // Chỉ vẽ bbox khi đang xem đúng ảnh mà toạ độ bám vào (ảnh đã OCR).
  const boxesOnThisView = view === "processed" && !!result?.ocr_image;

  // --- Vẽ ảnh + bbox lên canvas ---
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
      ctx.strokeStyle = active ? "#ff3b30" : "#00c853";
      ctx.fillStyle = active ? "rgba(255,59,48,0.18)" : "rgba(0,200,83,0.12)";
      ctx.fill();
      ctx.stroke();
    });
  }, [imgVersion, result, hovered, showBoxes, boxesOnThisView]);

  const healthColor =
    health === "ok" ? "#00c853" : health === "checking" ? "#ff9800" : "#ff3b30";
  const pm = preResult?.meta || result?.preprocess;

  // Nhóm record (kèm chỉ số phẳng để hover khớp bbox) theo số cột.
  const recordsByColumn = {};
  (result?.results || []).forEach((rec, idx) => {
    (recordsByColumn[rec.column] ||= []).push({ rec, idx });
  });

  return (
    <div className="wrap">
      <header>
        <h1>🪵 OCR Mộc Bản</h1>
        <div className="apirow">
          <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} spellCheck={false} />
          <button onClick={() => { checkHealth(); loadOptions(); }}>Health</button>
          <span className="dot" style={{ background: healthColor }} />
          <span className="hstatus">{health}</span>
        </div>
      </header>

      <div
        className="drop"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); onPick(e.dataTransfer.files?.[0]); }}
        onClick={() => document.getElementById("fileInput").click()}
      >
        <input id="fileInput" type="file" accept="image/*" hidden
          onChange={(e) => onPick(e.target.files?.[0])} />
        {file ? <span>📄 {file.name}</span> : <span>Kéo-thả ảnh ván khắc vào đây hoặc bấm để chọn</span>}
      </div>

      {/* Bảng điều khiển tiền xử lý */}
      <fieldset className="controls">
        <legend>
          <label className="chk">
            <input type="checkbox" checked={params.preprocess}
              onChange={(e) => setParam("preprocess", e.target.checked)} />
            Tiền xử lý mộc bản
          </label>
        </legend>
        <div className={"grid" + (params.preprocess ? "" : " off")}>
          <Field label="Stage (đầu vào OCR)">
            <select value={params.stage} onChange={(e) => setParam("stage", e.target.value)}>
              {serverOpts.stages.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Lật (flip)">
            <select value={params.flip} onChange={(e) => setParam("flip", e.target.value)}>
              {serverOpts.flip_directions.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Khử nhiễu">
            <select value={params.noise_method} onChange={(e) => setParam("noise_method", e.target.value)}>
              {serverOpts.noise_methods.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Num label="Resize width" k="resize_width" params={params} setParam={setParam} step={100} />
          <Num label="Canny low" k="canny_low" params={params} setParam={setParam} />
          <Num label="Canny high" k="canny_high" params={params} setParam={setParam} />
          <Num label="Deskew range°" k="deskew_range" params={params} setParam={setParam} step={0.5} />
          <Num label="CLAHE clip" k="clahe_clip" params={params} setParam={setParam} step={0.5} />
          <Num label="CLAHE tile" k="clahe_tile" params={params} setParam={setParam} />
          <button className="reset" onClick={() => setParams(DEFAULT_PARAMS)}>Mặc định</button>
        </div>
      </fieldset>

      <div className="actions">
        <button className="ghost" onClick={runPreprocess}
          disabled={!file || loading || !params.preprocess}
          title={!params.preprocess ? "Bật tiền xử lý để dùng" : ""}>
          {loading ? "Đang xử lý..." : "Chạy tiền xử lý"}
        </button>
        <button className="primary" onClick={runOcr} disabled={!file || loading}>
          {loading ? "Đang nhận dạng..." : "Chạy OCR"}
        </button>
        <label className="chk">
          <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
          Hiện bbox
        </label>
        {processedSrc && (
          <div className="seg">
            <button className={view === "processed" ? "on" : ""} onClick={() => setView("processed")}>
              Ảnh đã xử lý
            </button>
            <button className={view === "original" ? "on" : ""} onClick={() => setView("original")}>
              Ảnh gốc
            </button>
          </div>
        )}
        {result && (
          <span className="meta">{result.results?.length || 0} dòng · {result._ms} ms</span>
        )}
      </div>

      {pm && (
        <div className="premeta">
          {pm.applied ? (
            <>
              stage=<b>{pm.stage}</b> · góc detect=<b>{pm.auto_detected ? pm.strategy : "không"}</b>
              {" "}· nghiêng=<b>{pm.skew_angle}°</b> · {pm.input_shape} → <b>{pm.output_shape}</b>
            </>
          ) : <>tiền xử lý: <b>tắt</b></>}
        </div>
      )}

      {error && <div className="error">⚠️ {error}</div>}

      <div className="main">
        <div className="canvasbox">
          {displaySrc ? (
            <>
              <img ref={imgRef} src={displaySrc} alt="" style={{ display: "none" }}
                onLoad={() => setImgVersion((v) => v + 1)} />
              <canvas ref={canvasRef} />
            </>
          ) : (
            <div className="placeholder">Chưa có ảnh</div>
          )}
        </div>

        <div className="panel">
          <div className="panelhead">
            <h3>Kết quả {result?.columns?.length ? `· ${result.columns.length} cột` : ""}</h3>
            {result?.results?.length > 0 && (
              <div className="seg sm">
                <button className={resultView === "columns" ? "on" : ""} onClick={() => setResultView("columns")}>Theo cột</button>
                <button className={resultView === "list" ? "on" : ""} onClick={() => setResultView("list")}>Danh sách</button>
              </div>
            )}
          </div>

          {!result?.results?.length ? (
            <p className="muted">Chưa có kết quả.</p>
          ) : resultView === "columns" ? (
            // Cột PHẢI -> TRÁI (row-reverse), trong cột chữ dọc trên -> dưới.
            <div className="columns">
              {result.columns.map((col) => (
                <div className="col" key={col.index}>
                  <div className="colhead">{col.index}</div>
                  <div className="coltext">
                    {recordsByColumn[col.index]?.map(({ rec, idx }) => (
                      <span key={idx} className={hovered === idx ? "hl" : ""}
                        title={`${(rec.confidence * 100).toFixed(1)}%`}
                        onMouseEnter={() => setHovered(idx)} onMouseLeave={() => setHovered(null)}>
                        {rec.text}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <ol className="list">
              {result.results.map((it, i) => (
                <li key={i} className={hovered === i ? "hl" : ""}
                  onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
                  <span className="cidx">c{it.column}</span>
                  <span className="txt">{it.text}</span>
                  {it.confidence != null && (
                    <span className="conf">{(it.confidence * 100).toFixed(1)}%</span>
                  )}
                </li>
              ))}
            </ol>
          )}

          {result?.full_text && (
            <div className="fulltext">
              <div className="ftbar">
                <span>full_text</span>
                <button onClick={() => navigator.clipboard.writeText(result.full_text)}>Copy</button>
              </div>
              <pre>{result.full_text}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Num({ label, k, params, setParam, step = 1 }) {
  return (
    <Field label={label}>
      <input type="number" step={step} value={params[k]}
        onChange={(e) => setParam(k, e.target.value === "" ? "" : Number(e.target.value))} />
    </Field>
  );
}
