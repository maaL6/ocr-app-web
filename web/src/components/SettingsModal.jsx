import { useState } from "react";
import { Modal, Spinner } from "../ui.jsx";

export default function SettingsModal({ apiBase, health, checking, onChangeApiBase, onCheck, onClose }) {
  const [draft, setDraft] = useState(apiBase);

  const apply = () => {
    const trimmed = draft.trim().replace(/\/+$/, "");
    onChangeApiBase(trimmed);
    onCheck(trimmed);
  };

  return (
    <Modal title="Cài đặt máy chủ" onClose={onClose} width={460}>
      <div className="form-group">
        <label htmlFor="api-url">Địa chỉ máy chủ OCR (API)</label>
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
            {checking ? <Spinner size={14} /> : "Kiểm tra"}
          </button>
        </div>
      </div>

      <div className={`settings-status settings-status-${health || "unknown"}`}>
        <span className={`health-dot health-${health || "unknown"}`} />
        {health === "ok" && "Máy chủ hoạt động bình thường."}
        {health === "down" && "Không kết nối được máy chủ — kiểm tra Docker đã chạy chưa."}
        {health === "checking" && "Đang kiểm tra kết nối…"}
        {!health && "Chưa kiểm tra."}
      </div>

      <p className="settings-hint">
        Giá trị mặc định lấy từ biến môi trường <code>VITE_API_BASE</code> khi build. Thay đổi ở đây
        chỉ áp dụng cho phiên làm việc hiện tại.
      </p>
    </Modal>
  );
}
