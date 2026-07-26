// Chuẩn hoá & thao tác dữ liệu OCR phía client.
//
// Kết quả nội bộ (result) có dạng:
//   {
//     results: [{ text, confidence, bbox, column, aiAligned, glyphs: [Glyph] }],
//     columns: [{ index, text, avg_score }],
//     full_text, ocr_image, preprocess,
//     ai: { requested, applied, fallback } | null,
//   }
// Glyph:
//   {
//     ch,        // ký tự đang hiển thị (sau AI + sau khi người dùng sửa)
//     conf,      // độ tin cậy của ch (null nếu không rõ)
//     rawCh,     // ký tự OCR gốc (trước hậu xử lý)
//     rawConf,   // độ tin cậy OCR gốc
//     aiCh,      // ký tự SikuBERT đề xuất (=== rawCh nếu AI không đổi)
//     candidates,// [{char, confidence}] top-k từ decoder (để popover gợi ý)
//     bbox,      // bbox 4 điểm của ký tự trên ảnh OCR (nếu backend trả)
//   }
// aiChanged = aiCh !== rawCh; userEdited = ch !== aiCh.

const MAX_CANDIDATES = 6;

function splitChars(text) {
  // Array.from tách đúng theo code point (chữ Hán mở rộng nằm ngoài BMP).
  return Array.from(text || "");
}

function compactCandidates(list) {
  if (!Array.isArray(list)) return [];
  return list
    .filter((c) => c && typeof c.char === "string" && c.confidence != null)
    .slice(0, MAX_CANDIDATES)
    .map((c) => ({ char: c.char, confidence: Number(c.confidence) }));
}

function glyphsFromRecord(rec) {
  const chars = splitChars(rec.text);
  const perChar = Array.isArray(rec.per_char_confidences) ? rec.per_char_confidences : null;
  const detail = Array.isArray(rec.chars) && rec.chars.length === chars.length ? rec.chars : null;

  return chars.map((ch, i) => {
    const d = detail?.[i];
    const conf = d?.confidence ?? perChar?.[i] ?? null;
    const num = conf != null ? Number(conf) : null;
    return {
      ch,
      conf: num,
      rawCh: ch,
      rawConf: num,
      aiCh: ch,
      aiConf: num,
      candidates: compactCandidates(d?.candidates),
      bbox: d?.bbox ?? null,
    };
  });
}

/** Chuẩn hoá response /ocr (hoặc ocr_result đã lưu trong lịch sử). */
export function normalizeRaw(json) {
  const results = (json.results || []).map((rec) => ({
    text: rec.text,
    confidence: rec.confidence != null ? Number(rec.confidence) : null,
    bbox: rec.bbox || null,
    column: rec.column ?? 1,
    aiAligned: false,
    glyphs: glyphsFromRecord(rec),
  }));
  const derived = rebuildDerived(results);
  return {
    results,
    ...derived,
    ocr_image: json.ocr_image || null,
    preprocess: json.preprocess || { applied: false },
    ai: null,
  };
}

function bboxClose(a, b, tol = 8) {
  if (!a?.length || !b?.length) return false;
  return Math.abs(a[0][0] - b[0][0]) <= tol && Math.abs(a[0][1] - b[0][1]) <= tol;
}

/**
 * Response /ocr-postprocess khi SikuBERT lỗi sẽ trả nguyên văn kết quả /ocr
 * (kèm char_candidates mà schema sạch không bao giờ có) — dùng làm dấu hiệu.
 */
export function isPostprocessFallback(ppJson) {
  const first = ppJson?.results?.[0];
  return !!first && Object.prototype.hasOwnProperty.call(first, "char_candidates");
}

/**
 * Ghép kết quả gốc (/ocr) với bản BERT (/ocr-postprocess) theo chỉ số dòng.
 * Hai lời gọi cùng một ảnh nên thứ tự dòng trùng nhau; vẫn kiểm tra độ dài
 * text + bbox từng dòng, dòng nào lệch thì giữ nguyên bản gốc.
 */
export function mergeAI(rawJson, ppJson) {
  const base = normalizeRaw(rawJson);
  const ppResults = ppJson?.results || [];

  let alignedCount = 0;
  base.results.forEach((rec, i) => {
    const pp = ppResults[i];
    if (!pp) return;
    const corrected = splitChars(pp.text);
    if (corrected.length !== rec.glyphs.length) return;
    if (rec.bbox && pp.bbox && !bboxClose(rec.bbox, pp.bbox)) return;

    const ppConf = Array.isArray(pp.per_char_confidences) ? pp.per_char_confidences : null;
    rec.aiAligned = true;
    alignedCount += 1;
    rec.confidence = pp.confidence != null ? Number(pp.confidence) : rec.confidence;
    rec.glyphs = rec.glyphs.map((g, j) => {
      const aiCh = corrected[j];
      const conf = ppConf?.[j] ?? g.conf;
      const num = conf != null ? Number(conf) : null;
      return {
        ...g,
        ch: aiCh,
        aiCh,
        aiConf: num,
        conf: num,
      };
    });
    rec.text = rec.glyphs.map((g) => g.ch).join("");
  });

  const derived = rebuildDerived(base.results);
  return {
    ...base,
    ...derived,
    ai: {
      requested: true,
      applied: alignedCount > 0,
      fallback: false,
      changedCount: countAiChanges(base.results),
    },
  };
}

export function countAiChanges(results) {
  let n = 0;
  results.forEach((rec) =>
    rec.glyphs.forEach((g) => {
      if (g.aiCh !== g.rawCh) n += 1;
    })
  );
  return n;
}

/** Tâm dọc của bbox — khớp cách server sắp dòng trong cột (theo cy). */
export function bboxCenterY(rec) {
  if (!rec.bbox?.length) return 0;
  return rec.bbox.reduce((s, p) => s + p[1], 0) / rec.bbox.length;
}

/** Dựng lại columns + full_text từ results (sau khi chỉnh sửa). */
export function rebuildDerived(results) {
  const byCol = new Map();
  results.forEach((rec) => {
    const c = rec.column ?? 1;
    if (!byCol.has(c)) byCol.set(c, []);
    byCol.get(c).push(rec);
  });

  const columns = [...byCol.keys()]
    .sort((a, b) => a - b)
    .map((idx) => {
      const recs = byCol.get(idx);
      // Trong cột đọc trên → dưới; nếu có bbox thì sắp theo tâm dọc.
      if (recs.every((r) => r.bbox?.length)) {
        recs.sort((a, b) => bboxCenterY(a) - bboxCenterY(b));
      }
      const scored = recs.filter((r) => r.confidence != null);
      return {
        index: idx,
        text: recs.map((r) => r.text).join(""),
        avg_score: scored.length
          ? scored.reduce((s, r) => s + r.confidence, 0) / scored.length
          : null,
      };
    });

  return { columns, full_text: columns.map((c) => c.text).join("\n") };
}

/** Người dùng chọn/nhập một ký tự thay thế. */
export function applyGlyphEdit(result, recIdx, glyphIdx, newChar) {
  const results = result.results.map((rec, i) => {
    if (i !== recIdx) return rec;
    const glyphs = rec.glyphs.map((g, j) => {
      if (j !== glyphIdx) return g;
      const backToAi = newChar === g.aiCh;
      return {
        ...g,
        ch: newChar,
        // Người dùng đã xác nhận → coi như chắc chắn; quay về đề xuất cũ thì
        // trả lại độ tin cậy gốc (aiConf/rawConf được giữ riêng, không bị
        // ghi đè bởi các lần sửa tay trước đó).
        conf: backToAi ? (g.aiCh === g.rawCh ? g.rawConf : g.aiConf ?? g.conf) : 1.0,
      };
    });
    return { ...rec, glyphs, text: glyphs.map((g) => g.ch).join("") };
  });
  return { ...result, results, ...rebuildDerived(results) };
}

/** Sửa cả dòng (đổi text tự do và/hoặc chuyển cột). */
export function applyLineEdit(result, recIdx, { text, column }) {
  const results = result.results.map((rec, i) => {
    if (i !== recIdx) return rec;
    const nextText = text != null ? text : rec.text;
    const nextCol = column != null ? Number(column) : rec.column;
    let glyphs = rec.glyphs;
    if (nextText !== rec.text) {
      const chars = splitChars(nextText);
      glyphs = chars.map((ch, j) => {
        const old = rec.glyphs[j];
        // Giữ lịch sử (rawCh/aiCh/candidates/bbox) ở các vị trí còn glyph cũ
        // để bản "Gốc OCR" và popover gợi ý không bị mất sau khi sửa dòng.
        if (old) {
          if (old.ch === ch) return old;
          return { ...old, ch, conf: 1.0 };
        }
        return {
          ch, conf: 1.0, rawCh: ch, rawConf: null, aiCh: ch, aiConf: null,
          candidates: [], bbox: null,
        };
      });
    }
    return { ...rec, glyphs, text: nextText, column: nextCol };
  });
  return { ...result, results, ...rebuildDerived(results) };
}

// --- Heatmap độ tin cậy ---

export const HEAT_MID = 0.85;
export const HEAT_LOW = 0.6;

export function heatLevel(conf) {
  if (conf == null) return "none";
  if (conf >= HEAT_MID) return "hi";
  if (conf >= HEAT_LOW) return "mid";
  return "low";
}

// --- Thống kê & xuất ---

export function resultStats(result) {
  if (!result) return null;
  const nChars = result.results.reduce((s, r) => s + r.glyphs.length, 0);
  return { nChars, nLines: result.results.length, nCols: result.columns.length };
}

/** Bản gọn để lưu server / xuất JSON (bỏ candidates cho nhẹ). */
export function toPlainResult(result) {
  return {
    results: result.results.map((rec) => ({
      text: rec.text,
      confidence: rec.confidence,
      bbox: rec.bbox,
      column: rec.column,
      per_char_confidences: rec.glyphs.map((g) => g.conf ?? rec.confidence ?? 0),
    })),
    columns: result.columns,
    full_text: result.full_text,
    preprocess: result.preprocess || { applied: false },
  };
}

function download(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadText(filename, text) {
  download(filename, new Blob([text], { type: "text/plain;charset=utf-8" }));
}

export function downloadJson(filename, obj) {
  download(
    filename,
    new Blob([JSON.stringify(obj, null, 2)], { type: "application/json;charset=utf-8" })
  );
}

export function safeFilename(name, ext) {
  const base = (name || "ket-qua-ocr").replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "-");
  return `${base}.${ext}`;
}
