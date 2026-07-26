import { useEffect, useRef, useState } from "react";
import { Modal } from "../ui.jsx";

const GOOGLE_CLIENT_ID =
  "316323533715-u77bsr5qbo7p6b42g161cvcvlojfqbm9.apps.googleusercontent.com";

export default function AuthModal({ mode, onSwitchMode, error, onSubmit, onGoogleCredential, onClose }) {
  const [form, setForm] = useState({ email: "", password: "", fullname: "", phone_number: "" });
  const [submitting, setSubmitting] = useState(false);
  // Giữ callback mới nhất trong ref để effect init Google không phải chạy lại
  // (và không nhân đôi nút) mỗi khi App re-render.
  const credentialCbRef = useRef(onGoogleCredential);
  credentialCbRef.current = onGoogleCredential;

  const setField = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(form);
    } finally {
      setSubmitting(false);
    }
  };

  // Nút Google chỉ hiển thị ở chế độ đăng nhập
  useEffect(() => {
    if (mode !== "login" || !window.google) return;
    try {
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => credentialCbRef.current(response.credential),
      });
      const slot = document.getElementById("googleBtn");
      if (slot) {
        slot.innerHTML = "";
        // GSI render iframe rộng cố định — đo container để không bị cắt trên
        // màn hình hẹp (GSI chấp nhận 200–400px).
        const width = Math.max(200, Math.min(360, slot.offsetWidth || 360));
        window.google.accounts.id.renderButton(slot, { theme: "outline", size: "large", width });
      }
    } catch (e) {
      console.error("Lỗi Google Init:", e);
    }
  }, [mode]);

  return (
    <Modal title={mode === "login" ? "Đăng nhập" : "Tạo tài khoản"} onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form className="modal-form" onSubmit={submit}>
        {mode === "register" && (
          <>
            <div className="form-group">
              <label htmlFor="auth-fullname">Họ và tên</label>
              <input
                id="auth-fullname"
                type="text"
                name="fullname"
                value={form.fullname}
                onChange={setField}
                required
                placeholder="Ví dụ: Nguyễn Văn A"
              />
            </div>
            <div className="form-group">
              <label htmlFor="auth-phone">Số điện thoại</label>
              <input
                id="auth-phone"
                type="tel"
                name="phone_number"
                value={form.phone_number}
                onChange={setField}
                placeholder="Không bắt buộc"
              />
            </div>
          </>
        )}
        <div className="form-group">
          <label htmlFor="auth-email">Địa chỉ email</label>
          <input
            id="auth-email"
            type="email"
            name="email"
            value={form.email}
            onChange={setField}
            required
            placeholder="ten@example.com"
          />
        </div>
        <div className="form-group">
          <label htmlFor="auth-password">Mật khẩu</label>
          <input
            id="auth-password"
            type="password"
            name="password"
            value={form.password}
            onChange={setField}
            required
            placeholder="••••••••"
          />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? "Đang xử lý…" : mode === "login" ? "Đăng nhập" : "Đăng ký tài khoản"}
        </button>
      </form>

      {mode === "login" && (
        <>
          <div className="auth-divider">
            <span>Hoặc đăng nhập bằng</span>
          </div>
          <div id="googleBtn" className="google-btn-slot" />
        </>
      )}

      <div className="modal-footer-text">
        {mode === "login" ? (
          <>
            Chưa có tài khoản?{" "}
            <button type="button" className="link-btn" onClick={() => onSwitchMode("register")}>
              Đăng ký ngay
            </button>
          </>
        ) : (
          <>
            Đã có tài khoản?{" "}
            <button type="button" className="link-btn" onClick={() => onSwitchMode("login")}>
              Đăng nhập
            </button>
          </>
        )}
      </div>
    </Modal>
  );
}
