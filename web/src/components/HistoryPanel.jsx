import { Spinner } from "../ui.jsx";
import { useI18n } from "../i18n.jsx";

export default function HistoryPanel({ docs, loading, selectedDocId, onOpen, onDelete }) {
  const { t, language } = useI18n();
  return (
    <div className="card history-card">
      <h2 className="card-title">{t("historyTitle", "Lịch sử quét tài liệu")}</h2>

      {loading ? (
        <div className="loading-indicator">
          <Spinner /> {t("loadingHistory", "Đang tải lịch sử…")}
        </div>
      ) : docs.length === 0 ? (
        <p className="empty-state">
          {t("noHistory", "Chưa có tài liệu nào được lưu. Chạy OCR ở tab Nhận dạng rồi chọn Lưu vào tài khoản.")}
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
                aria-label={`${t("open", "Mở")} ${doc.title || `${t("document", "Tài liệu")} #${doc.id}`}`}
              >
                <span className="item-title">{doc.title || `${t("document", "Tài liệu")} #${doc.id}`}</span>
                <span className="item-snippet cjk">{doc.full_text || `(${t("empty", "Trống")})`}</span>
                <span className="item-meta">
                  {new Date(doc.created_at).toLocaleString(language === "en" ? "en-GB" : "vi-VN")}
                </span>
              </button>
              <button
                className="icon-btn icon-btn-danger"
                title={t("deleteDocument", "Xóa tài liệu")}
                aria-label={`${t("delete", "Xóa")} ${doc.title || `${t("document", "tài liệu")} #${doc.id}`}`}
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
