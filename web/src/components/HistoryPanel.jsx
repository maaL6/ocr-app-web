import { Spinner } from "../ui.jsx";

export default function HistoryPanel({ docs, loading, selectedDocId, onOpen, onDelete }) {
  return (
    <div className="card history-card">
      <h2 className="card-title">Lịch sử quét tài liệu</h2>

      {loading ? (
        <div className="loading-indicator">
          <Spinner /> Đang tải lịch sử…
        </div>
      ) : docs.length === 0 ? (
        <p className="empty-state">
          Chưa có tài liệu nào được lưu. Chạy OCR ở tab <b>Nhận dạng</b> rồi chọn{" "}
          <b>Lưu vào tài khoản</b>.
        </p>
      ) : (
        <div className="list-group">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className={`list-group-item ${selectedDocId === doc.id ? "active" : ""}`}
            >
              <button
                className="item-info"
                onClick={() => onOpen(doc.id)}
                aria-label={`Mở ${doc.title || `tài liệu #${doc.id}`}`}
              >
                <span className="item-title">{doc.title || `Tài liệu #${doc.id}`}</span>
                <span className="item-snippet cjk">{doc.full_text || "(Trống)"}</span>
                <span className="item-meta">
                  {new Date(doc.created_at).toLocaleString("vi-VN")}
                </span>
              </button>
              <button
                className="icon-btn icon-btn-danger"
                title="Xóa tài liệu"
                aria-label={`Xóa ${doc.title || `tài liệu #${doc.id}`}`}
                onClick={() => onDelete(doc)}
              >
                🗑
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
