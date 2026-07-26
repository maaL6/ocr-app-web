import { useCallback, useEffect, useRef, useState } from "react";
import { Segmented, Spinner } from "../ui.jsx";
import { heatLevel } from "../ocr.js";

const ZOOM_STEPS = [0.15, 0.25, 0.35, 0.5, 0.65, 0.8, 1, 1.25, 1.5, 2, 3];

function pointInPoly(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polyArea(poly) {
  let s = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    s += (poly[j][0] + poly[i][0]) * (poly[j][1] - poly[i][1]);
  }
  return Math.abs(s / 2);
}

const PHASE_LABEL = {
  pre: "Đang tiền xử lý ảnh…",
  ocr: "Đang nhận dạng chữ Hán…",
  ai: "Đang hiệu đính bằng SikuBERT…",
};

export default function ViewerPanel({
  displaySrc,
  results, // dòng OCR (để vẽ bbox) — chỉ khi đang xem ảnh OCR
  boxesEnabled,
  showBoxes,
  onToggleBoxes,
  hovered,
  onHover,
  selected,
  onSelect,
  view,
  onView,
  hasProcessed,
  metaCaption,
  phase,
  onPickFile,
  aiApplied,
}) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const stageRef = useRef(null);
  const [imgVersion, setImgVersion] = useState(0);
  const [zoom, setZoom] = useState("fit"); // "fit" | số
  const [fitScale, setFitScale] = useState(1);

  const naturalW = imgRef.current?.naturalWidth || 0;
  const scale = zoom === "fit" ? fitScale : zoom;

  // Tính tỷ lệ vừa khung khi ảnh/khung đổi kích thước
  const computeFit = useCallback(() => {
    const stage = stageRef.current;
    const img = imgRef.current;
    if (!stage || !img?.naturalWidth) return;
    const avail = stage.clientWidth - 28; // trừ padding
    setFitScale(Math.min(Math.max(avail / img.naturalWidth, 0.05), 1.5));
  }, []);

  useEffect(() => {
    computeFit();
    const stage = stageRef.current;
    if (!stage || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(computeFit);
    ro.observe(stage);
    return () => ro.disconnect();
  }, [computeFit, imgVersion]);

  // Ảnh đổi → về chế độ vừa khung
  useEffect(() => {
    setZoom("fit");
  }, [displaySrc]);

  // Vẽ ảnh + bbox
  useEffect(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);

    if (!showBoxes || !boxesEnabled || !results?.length) return;

    const tracePoly = (poly) => {
      ctx.beginPath();
      poly.forEach(([x, y], k) => (k === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.closePath();
    };

    // Khung DÒNG: màu theo độ tin cậy trung bình của cả dòng
    // (xanh ≥85%, hổ phách 60–85%, đỏ <60%).
    const LINE_STYLE = {
      hi: { stroke: "rgba(79, 122, 63, 0.9)", fill: null },
      mid: { stroke: "#b07a17", fill: "rgba(176, 122, 23, 0.10)" },
      low: { stroke: "#b23b2e", fill: "rgba(178, 59, 46, 0.12)" },
      none: { stroke: "rgba(88, 66, 48, 0.55)", fill: null },
    };
    results.forEach((rec, i) => {
      const poly = rec.bbox;
      if (!poly?.length) return;
      const active = hovered === i || selected?.recIdx === i;
      const style = LINE_STYLE[heatLevel(rec.confidence)] || LINE_STYLE.none;
      tracePoly(poly);
      if (active) {
        ctx.fillStyle = "rgba(224, 85, 69, 0.18)";
        ctx.fill();
      } else if (style.fill) {
        ctx.fillStyle = style.fill;
        ctx.fill();
      }
      ctx.lineWidth = active ? 4 : 2;
      ctx.strokeStyle = active ? "#e05545" : style.stroke;
      ctx.stroke();
    });

    // KHOANH riêng ký tự độ tin cậy thấp (<60%) bằng vòng xanh dương —
    // màu khác hẳn hệ xanh/vàng/đỏ của khung dòng để nhìn là biết ngay
    // "chữ này cần soát", kể cả khi nằm trong dòng điểm cao.
    results.forEach((rec) => {
      rec.glyphs?.forEach((g) => {
        if (!g.bbox?.length || heatLevel(g.conf) !== "low") return;
        const xs = g.bbox.map((p) => p[0]);
        const ys = g.bbox.map((p) => p[1]);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
        const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const rx = (Math.max(...xs) - Math.min(...xs)) / 2 + 5;
        const ry = (Math.max(...ys) - Math.min(...ys)) / 2 + 5;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(37, 99, 235, 0.10)";
        ctx.fill();
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = "#2563eb";
        ctx.stroke();
      });
    });

    // Khung ký tự đang chọn (nếu backend trả bbox theo ký tự)
    const glyph = selected != null ? results[selected.recIdx]?.glyphs?.[selected.glyphIdx] : null;
    if (glyph?.bbox?.length) {
      ctx.beginPath();
      glyph.bbox.forEach(([x, y], k) => (k === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.closePath();
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#e08a1e";
      ctx.stroke();
    }
  }, [imgVersion, results, hovered, selected, showBoxes, boxesEnabled, displaySrc]);

  // Toạ độ chuột → toạ độ ảnh gốc
  const eventToImage = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    return [
      ((e.clientX - rect.left) / rect.width) * canvas.width,
      ((e.clientY - rect.top) / rect.height) * canvas.height,
    ];
  };

  const hitTest = (x, y) => {
    if (!results?.length) return null;
    let best = null;
    let bestArea = Infinity;
    results.forEach((rec, i) => {
      if (!rec.bbox?.length) return;
      if (!pointInPoly(x, y, rec.bbox)) return;
      const area = polyArea(rec.bbox);
      if (area < bestArea) {
        bestArea = area;
        best = i;
      }
    });
    return best;
  };

  const onCanvasClick = (e) => {
    if (!boxesEnabled) return;
    const pt = eventToImage(e);
    if (!pt) return;
    const recIdx = hitTest(pt[0], pt[1]);
    if (recIdx == null) {
      onSelect(null);
      return;
    }
    // Tìm đúng ký tự nếu có bbox theo ký tự
    let glyphIdx = null;
    results[recIdx].glyphs?.forEach((g, j) => {
      if (glyphIdx == null && g.bbox?.length && pointInPoly(pt[0], pt[1], g.bbox)) glyphIdx = j;
    });
    onSelect({ recIdx, glyphIdx: glyphIdx ?? 0 });
  };

  const onCanvasMove = (e) => {
    if (!boxesEnabled) return;
    const pt = eventToImage(e);
    if (!pt) return;
    onHover(hitTest(pt[0], pt[1]));
  };

  const zoomBy = (dir) => {
    const cur = scale;
    const next =
      dir > 0
        ? ZOOM_STEPS.find((z) => z > cur + 0.01)
        : [...ZOOM_STEPS].reverse().find((z) => z < cur - 0.01);
    if (next) setZoom(next);
  };

  return (
    <section className="panel viewer-panel">
      <div className="panel-head">
        <h2>Ảnh ván khắc</h2>
        {metaCaption && <span className="panel-caption">{metaCaption}</span>}
        <div className="panel-head-spacer" />
        {hasProcessed && (
          <Segmented
            small
            value={view}
            onChange={onView}
            options={[
              { value: "processed", label: "Đã xử lý" },
              { value: "original", label: "Ảnh gốc" },
            ]}
          />
        )}
        <div className="viewer-tools">
          <div className="zoom-control">
            <button onClick={() => zoomBy(-1)} aria-label="Thu nhỏ" disabled={!displaySrc}>
              −
            </button>
            <button
              className="zoom-level"
              onClick={() => setZoom(zoom === "fit" ? 1 : "fit")}
              title={zoom === "fit" ? "Xem kích thước thật (100%)" : "Vừa khung"}
              disabled={!displaySrc}
            >
              {zoom === "fit" ? `${Math.round(fitScale * 100)}%` : `${Math.round(scale * 100)}%`}
            </button>
            <button onClick={() => zoomBy(1)} aria-label="Phóng to" disabled={!displaySrc}>
              +
            </button>
          </div>
          {boxesEnabled && (
            <button
              className={`icon-btn ${showBoxes ? "icon-btn-on" : ""}`}
              onClick={onToggleBoxes}
              title={showBoxes ? "Ẩn khung chữ" : "Hiện khung chữ"}
              aria-pressed={showBoxes}
            >
              ▣
            </button>
          )}
        </div>
      </div>

      <div
        className="stage"
        ref={stageRef}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          onPickFile(e.dataTransfer.files?.[0]);
        }}
      >
        {displaySrc ? (
          <>
            <img
              ref={imgRef}
              src={displaySrc}
              alt=""
              style={{ display: "none" }}
              onLoad={() => {
                setImgVersion((v) => v + 1);
                computeFit();
              }}
            />
            <canvas
              ref={canvasRef}
              style={{ width: naturalW ? naturalW * scale : undefined, cursor: boxesEnabled ? "crosshair" : "default" }}
              onClick={onCanvasClick}
              onMouseMove={onCanvasMove}
              onMouseLeave={() => onHover(null)}
            />
          </>
        ) : (
          <button className="stage-empty" onClick={() => onPickFile(undefined, true)}>
            <span className="stage-empty-icon">🪵</span>
            <span className="stage-empty-title">Kéo–thả ảnh ván khắc vào đây</span>
            <span className="stage-empty-sub">hoặc bấm để chọn tệp ảnh</span>
          </button>
        )}

        {phase && (
          <div className="stage-loading">
            <Spinner size={26} />
            <span>{PHASE_LABEL[phase] || "Đang xử lý…"}</span>
          </div>
        )}
      </div>

      <div className="viewer-legend">
        <span className="legend-label">Khung dòng:</span>
        <span className="legend-item">
          <span className="legend-swatch heat-swatch-hi" /> ≥ 85%
        </span>
        <span className="legend-item">
          <span className="legend-swatch heat-swatch-mid" /> 60–85%
        </span>
        <span className="legend-item">
          <span className="legend-swatch heat-swatch-low" /> Dưới 60%
        </span>
        <span className="legend-item">
          <span className="legend-swatch legend-swatch-char" /> Ký tự &lt; 60%
        </span>
        {aiApplied && (
          <span className="legend-item">
            <span className="legend-swatch legend-swatch-ai" /> AI đã sửa
          </span>
        )}
      </div>
    </section>
  );
}
