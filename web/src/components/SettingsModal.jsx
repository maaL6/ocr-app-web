import { useState } from "react";
import { Modal, Spinner } from "../ui.jsx";
import { useI18n } from "../i18n.jsx";

export default function SettingsModal({ apiBase, health, checking, onChangeApiBase, onCheck, onClose }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(apiBase);

  const apply = () => {
    const trimmed = draft.trim().replace(/\/+$/, "");
    onChangeApiBase(trimmed);
    onCheck(trimmed);
  };

  return (
    <Modal title={t("serverSettings", "Cài đặt máy chủ")} onClose={onClose} width={460}>
      <div className="form-group">
        <label htmlFor="api-url">{t("serverAddress", "Địa chỉ máy chủ OCR (API)")}</label>
        <div className="settings-row">
          <input
            id="api-url"
            type="url"
            value={draft}
            spellCheck={false}
            placeholder="http://localhost:8000"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && apply()}
          />
          <button className="btn btn-primary" onClick={apply} disabled={checking}>
            {checking ? <Spinner size={14} /> : t("check", "Kiểm tra")}
          </button>
        </div>
      </div>

      <div className={`settings-status settings-status-${health || "unknown"}`}>
        <span className={`health-dot health-${health || "unknown"}`} />
        {health === "ok" && t("serverOk", "Máy chủ hoạt động bình thường.")}
        {health === "down" && t("serverDown", "Không kết nối được máy chủ — kiểm tra Docker đã chạy chưa.")}
        {health === "checking" && t("checkingConnection", "Đang kiểm tra kết nối…")}
        {!health && t("notChecked", "Chưa kiểm tra.")}
      </div>

      <p className="settings-hint">
        {t("settingsHint", "Giá trị mặc định lấy từ biến môi trường VITE_API_BASE khi build. Thay đổi ở đây chỉ áp dụng cho phiên làm việc hiện tại.")}
      </p>
    </Modal>
  );
}
