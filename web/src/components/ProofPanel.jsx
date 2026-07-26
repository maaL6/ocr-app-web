import { useEffect, useMemo, useRef, useState } from "react";
import { Segmented } from "../ui.jsx";
import {
  heatLevel,
  bboxCenterY,
  downloadText,
  downloadJson,
  safeFilename,
  toPlainResult,
} from "../ocr.js";

function pct(p) {
  if (p == null) return "—";
  if (p >= 0.001) return `${(p * 100).toFixed(1)}%`;
  return "<0.1%";
}

/** Một ký tự trong bảng hiệu đính. */
function GlyphSpan({ g, recIdx, glyphIdx, aiView, hovered, selected, setHovered, setSelected }) {
  const isRaw = aiView === "raw";
  const ch = isRaw ? g.rawCh : g.ch;
  const conf = isRaw ? g.rawConf : g.conf;
  const heat = heatLevel(conf);
  const aiChanged = g.aiCh !== g.rawCh;
  const userEdited = g.ch !== g.aiCh;
  const isSel = !isRaw && selected?.recIdx === recIdx && selected?.glyphIdx === glyphIdx;

  const cls = [
    "glyph",
    heat === "mid" && "heat-mid",
    heat === "low" && "heat-low",
    !isRaw && aiChanged && "ai-fixed",
    !isRaw && userEdited && "user-edited",
    isSel && "sel",
    hovered === recIdx && "line-hl",
  ]
    .filter(Boolean)
    .join(" ");

  const title = isRaw
    ? `Bản gốc OCR · ${pct(conf)}`
    : [
        `Độ tin cậy: ${pct(conf)}`,
        aiChanged && `AI sửa: ${g.rawCh} → ${g.aiCh}`,
        userEdited && "Đã sửa tay",
        "Bấm để hiệu đính",
      ]
        .filter(Boolean)
        .join(" · ");

  return (
    <button
      id={!isRaw ? `glyph-${recIdx}-${glyphIdx}` : undefined}
      className={cls}
      title={title}
      onMouseEnter={() => setHovered(recIdx)}
      onMouseLeave={() => setHovered(null)}
      onClick={() => !isRaw && setSelected({ recIdx, glyphIdx })}
      disabled={isRaw}
    >
      {ch}
    </button>
  );
}

/** Popover chọn ký tự thay thế. */
function CandidateBox({ result, selected, aiView, onApplyGlyph, onClose }) {
  const [manual, setManual] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    setManual("");
  }, [selected?.recIdx, selected?.glyphIdx]);

  if (aiView === "raw" || selected == null) return null;
  const rec = result.results[selected.recIdx];
  const g = rec?.glyphs?.[selected.glyphIdx];
  if (!g) return null;

  const aiChanged = g.aiCh !== g.rawCh;
  const userEdited = g.ch !== g.aiCh;

  // Danh sách ứng viên: đề xuất AI trước (nếu có), rồi top-k decoder.
  const items = [];
  if (aiChanged) {
    const dec = g.candidates.find((c) => c.char === g.aiCh);
    items.push({ char: g.aiCh, confidence: g.conf ?? dec?.confidence ?? null, tag: "SikuBERT" });
  }
  g.candidates.forEach((c) => {
    if (!items.some((it) => it.char === c.char)) items.push({ char: c.char, confidence: c.confidence });
  });
  if (!items.some((it) => it.char === g.rawCh)) {
    items.push({ char: g.rawCh, confidence: g.rawConf, tag: aiChanged ? "OCR gốc" : undefined });
  }
  const maxConf = Math.max(...items.map((it) => it.confidence ?? 0), 1e-9);

  const apply = (ch) => {
    const first = Array.from(ch.trim())[0];
    if (first) onApplyGlyph(selected.recIdx, selected.glyphIdx, first);
  };

  return (
    <div className="candidate-box">
      <div className="candidate-head">
        <span className="candidate-big cjk">{g.ch}</span>
        <div className="candidate-meta">
          <div>
            Cột {rec.column} · vị trí {selected.glyphIdx + 1}/{rec.glyphs.length} · độ tin cậy{" "}
            <b>{pct(g.conf)}</b>
          </div>
          {aiChanged && (
            <div className="candidate-ai-note">
              SikuBERT sửa <b className="cjk">{g.rawCh}</b> ({pct(g.rawConf)}) →{" "}
              <b className="cjk">{g.aiCh}</b>
            </div>
          )}
          {userEdited && <div className="candidate-user-note">Bạn đã sửa tay ký tự này.</div>}
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Đóng bảng gợi ý">
          ✕
        </button>
      </div>

      <div className="candidate-list-label">Chọn chữ đúng</div>
      {items.length ? (
        <div className="candidate-list">
          {items.map((it) => (
            <button
              key={it.char}
              className={`candidate-item ${it.char === g.ch ? "current" : ""}`}
              onClick={() => apply(it.char)}
            >
              <span className="candidate-char cjk">{it.char}</span>
              <span className="candidate-bar">
                <span
                  style={{ width: `${Math.max((100 * (it.confidence ?? 0)) / maxConf, 2)}%` }}
                />
              </span>
              <span className="candidate-pct">{pct(it.confidence)}</span>
              {it.tag && <span className="candidate-tag">{it.tag}</span>}
            </button>
          ))}
        </div>
      ) : (
        <p className="candidate-empty">Không có gợi ý cho ký tự này.</p>
      )}

      <div className="candidate-manual">
        <input
          ref={inputRef}
          className="cjk"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && manual.trim() && apply(manual)}
          placeholder="Nhập chữ khác…"
          aria-label="Nhập ký tự thay thế"
        />
        <button className="btn btn-primary btn-sm" disabled={!manual.trim()} onClick={() => apply(manual)}>
          Áp dụng
        </button>
        {(userEdited || aiChanged) && (
          <button
            className="btn btn-ghost btn-sm"
            title="Trả ký tự về đúng kết quả OCR ban đầu"
            onClick={() => apply(g.rawCh)}
          >
            Về bản gốc
          </button>
        )}
      </div>
    </div>
  );
}

export default function ProofPanel({
  result,
  resultView,
  setResultView,
  aiView,
  setAiView,
  hovered,
  setHovered,
  selected,
  setSelected,
  onApplyGlyph,
  onLineEdit,
  exportBaseName,
  onToast,
}) {
  const [editingLine, setEditingLine] = useState(null);
  const [editText, setEditText] = useState("");
  const [editCol, setEditCol] = useState(1);

  // Kết quả bị thay (ảnh mới / chạy lại OCR) → đóng editor dòng đang mở để
  // không ghi đè văn bản cũ lên dòng của kết quả mới.
  useEffect(() => {
    setEditingLine(null);
  }, [result]);

  const aiApplied = !!result?.ai?.applied;
  const aiChangedCount = useMemo(() => {
    if (!result) return 0;
    let n = 0;
    result.results.forEach((r) => r.glyphs.forEach((g) => g.aiCh !== g.rawCh && n++));
    return n;
  }, [result]);

  // Gom dòng theo cột (phục vụ hiển thị cột dọc + toàn văn có highlight)
  const recordsByColumn = useMemo(() => {
    const map = new Map();
    (result?.results || []).forEach((rec, recIdx) => {
      const c = rec.column ?? 1;
      if (!map.has(c)) map.set(c, []);
      map.get(c).push({ rec, recIdx });
    });
    [...map.values()].forEach((list) => {
      if (list.every(({ rec }) => rec.bbox?.length)) {
        list.sort((a, b) => bboxCenterY(a.rec) - bboxCenterY(b.rec));
      }
    });
    return map;
  }, [result]);

  const colIndices = useMemo(
    () => [...recordsByColumn.keys()].sort((a, b) => a - b),
    [recordsByColumn]
  );

  // Scale cỡ chữ theo CỘT DÀI NHẤT: trong writing-mode dọc, cột cao quá khung
  // sẽ tự bẻ thành cột con thứ hai ngay trong cùng một ô ("2 cột chữ cho 1 ô").
  // Chọn font vừa đủ để cột dài nhất nằm gọn, và khóa chiều cao ô đúng bằng
  // nhu cầu để trình duyệt không bao giờ bẻ dòng.
  const { colFontSize, colBodyHeight } = useMemo(() => {
    let maxChars = 0;
    recordsByColumn.forEach((list) => {
      const n = list.reduce((s, { rec }) => s + rec.glyphs.length, 0);
      maxChars = Math.max(maxChars, n);
    });
    if (!maxChars) return { colFontSize: 25, colBodyHeight: undefined };
    const GLYPH_PAD = 2; // padding dọc 1px×2 của .glyph cộng vào mỗi ký tự
    const BODY_PAD = 24; // padding + border của .ocr-col-body
    const TARGET_H = 500; // chiều cao thân cột mong muốn (px)
    const size = Math.max(
      12,
      Math.min(25, Math.floor((TARGET_H - BODY_PAD) / maxChars) - GLYPH_PAD)
    );
    return {
      colFontSize: size,
      // Cao đúng bằng nội dung cột dài nhất (+đệm) — cột nào cũng 1 hàng dọc.
      colBodyHeight: maxChars * (size + GLYPH_PAD) + BODY_PAD + 4,
    };
  }, [recordsByColumn]);

  // Cuộn tới ký tự được chọn (ví dụ chọn từ canvas)
  useEffect(() => {
    if (selected == null) return;
    const el = document.getElementById(`glyph-${selected.recIdx}-${selected.glyphIdx}`);
    el?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  }, [selected]);

  const displayedFullText = useMemo(() => {
    if (!result) return "";
    if (aiView !== "raw") return result.full_text;
    return colIndices
      .map((c) =>
        recordsByColumn
          .get(c)
          .map(({ rec }) => rec.glyphs.map((g) => g.rawCh).join(""))
          .join("")
      )
      .join("\n");
  }, [result, aiView, colIndices, recordsByColumn]);

  const copyFullText = async () => {
    try {
      await navigator.clipboard.writeText(displayedFullText);
      onToast("success", "Đã sao chép toàn văn");
    } catch {
      onToast("error", "Không sao chép được", "Trình duyệt chặn quyền clipboard.");
    }
  };

  const startLineEdit = (recIdx) => {
    const rec = result.results[recIdx];
    setEditingLine(recIdx);
    setEditText(rec.text);
    setEditCol(rec.column ?? 1);
  };

  const saveLineEdit = () => {
    onLineEdit(editingLine, { text: editText, column: Number(editCol) || 1 });
    setEditingLine(null);
  };

  if (!result || result.results.length === 0) {
    return (
      <section className="panel proof-panel">
        <div className="panel-head">
          <h2>Kết quả &amp; hiệu đính</h2>
        </div>
        <p className="empty-state">
          {result ? (
            <>Không nhận dạng được chữ nào trong ảnh. Thử điều chỉnh tham số tiền xử lý.</>
          ) : (
            <>Chưa có dữ liệu nhận dạng. Tải ảnh lên và bấm <b>Chạy OCR</b>.</>
          )}
        </p>
      </section>
    );
  }

  return (
    <section className="panel proof-panel">
      <div className="panel-head">
        <h2>Kết quả &amp; hiệu đính</h2>
        <span className="panel-caption">({result.columns.length} cột)</span>
        {aiApplied && (
          <span className="ai-badge" title="Số ký tự SikuBERT đã thay so với OCR gốc">
            SikuBERT sửa {aiChangedCount} chữ
          </span>
        )}
        <div className="panel-head-spacer" />
        {aiApplied && (
          <Segmented
            small
            value={aiView}
            onChange={setAiView}
            options={[
              { value: "raw", label: "Gốc OCR" },
              { value: "final", label: "Đã sửa AI" },
            ]}
          />
        )}
        <Segmented
          small
          value={resultView}
          onChange={setResultView}
          options={[
            { value: "columns", label: "Theo cột" },
            { value: "list", label: "Danh sách" },
          ]}
        />
      </div>

      <div className="proof-body">
        {resultView === "columns" ? (
          <div className="ocr-columns">
            {colIndices.map((c) => (
              <div className="ocr-col" key={c}>
                <div className="ocr-col-header">{c}</div>
                <div
                  className="ocr-col-body"
                  style={{ fontSize: colFontSize, height: colBodyHeight }}
                >
                  {recordsByColumn.get(c).map(({ rec, recIdx }) => (
                    <span className="line-group" key={recIdx}>
                      {rec.glyphs.map((g, j) => (
                        <GlyphSpan
                          key={j}
                          g={g}
                          recIdx={recIdx}
                          glyphIdx={j}
                          aiView={aiView}
                          hovered={hovered}
                          selected={selected}
                          setHovered={setHovered}
                          setSelected={setSelected}
                        />
                      ))}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <ul className="ocr-list">
            {result.results.map((rec, recIdx) => (
              <li
                key={recIdx}
                className={`ocr-list-item ${hovered === recIdx ? "hl" : ""}`}
                onMouseEnter={() => setHovered(recIdx)}
                onMouseLeave={() => setHovered(null)}
              >
                <span className="ocr-list-col-badge">Cột {rec.column}</span>
                <span className="ocr-list-text">
                  {rec.glyphs.map((g, j) => (
                    <GlyphSpan
                      key={j}
                      g={g}
                      recIdx={recIdx}
                      glyphIdx={j}
                      aiView={aiView}
                      hovered={hovered}
                      selected={selected}
                      setHovered={setHovered}
                      setSelected={setSelected}
                    />
                  ))}
                </span>
                {rec.confidence != null && (
                  <span className={`ocr-list-confidence conf-${heatLevel(rec.confidence)}`}>
                    {pct(rec.confidence)}
                  </span>
                )}
                <button
                  className="icon-btn icon-btn-sm"
                  title="Sửa cả dòng / chuyển cột"
                  onClick={() => startLineEdit(recIdx)}
                >
                  ✎
                </button>
              </li>
            ))}
          </ul>
        )}

        {editingLine != null && (
          <div className="line-editor">
            <div className="line-editor-head">Sửa dòng (cột {result.results[editingLine]?.column})</div>
            <div className="line-editor-row">
              <input
                className="cjk"
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                aria-label="Nội dung dòng"
              />
              <input
                type="number"
                min={1}
                value={editCol}
                onChange={(e) => setEditCol(e.target.value)}
                title="Số cột"
                aria-label="Số cột"
              />
            </div>
            <div className="line-editor-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setEditingLine(null)}>
                Hủy
              </button>
              <button className="btn btn-primary btn-sm" onClick={saveLineEdit}>
                Lưu dòng
              </button>
            </div>
          </div>
        )}

        <CandidateBox
          result={result}
          selected={selected}
          aiView={aiView}
          onApplyGlyph={onApplyGlyph}
          onClose={() => setSelected(null)}
        />
      </div>

      <div className="fulltext">
        <div className="fulltext-head">
          <span className="fulltext-label">
            Toàn văn {aiView === "raw" ? "(bản gốc OCR)" : ""}
          </span>
          <div className="fulltext-actions">
            <button className="btn btn-ghost btn-sm" onClick={copyFullText}>
              ⧉ Sao chép
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => downloadText(safeFilename(exportBaseName, "txt"), result.full_text)}
              title="Tải toàn văn (bản hiện tại) dạng .txt"
            >
              ↓ .txt
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => downloadJson(safeFilename(exportBaseName, "json"), toPlainResult(result))}
              title="Tải kết quả đầy đủ (dòng, cột, độ tin cậy) dạng .json"
            >
              ↓ .json
            </button>
          </div>
        </div>
        <div className="fulltext-box cjk">
          {colIndices.map((c, i) => (
            <div key={c} className="fulltext-line">
              {recordsByColumn.get(c).map(({ rec, recIdx }) =>
                rec.glyphs.map((g, j) => {
                  const ch = aiView === "raw" ? g.rawCh : g.ch;
                  const marked = aiView !== "raw" && (g.aiCh !== g.rawCh || g.ch !== g.aiCh);
                  return marked ? (
                    <span
                      key={`${recIdx}-${j}`}
                      className="fulltext-corr"
                      title={`Gốc: ${g.rawCh}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelected({ recIdx, glyphIdx: j })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected({ recIdx, glyphIdx: j });
                        }
                      }}
                    >
                      {ch}
                    </span>
                  ) : (
                    ch
                  );
                })
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
