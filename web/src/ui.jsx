import { useEffect, useRef } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// --- Khung modal dùng chung: focus trap, đóng bằng Esc / click nền ---
export function Modal({ title, onClose, children, width = 440 }) {
  const contentRef = useRef(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const content = contentRef.current;

    // Chuyển focus vào modal khi mở
    const first = content?.querySelector(FOCUSABLE);
    (first || content)?.focus();

    const onKey = (e) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      // Giữ Tab/Shift+Tab trong modal (focus trap)
      if (e.key === "Tab" && content) {
        const focusables = [...content.querySelectorAll(FOCUSABLE)];
        if (!focusables.length) return;
        const firstEl = focusables[0];
        const lastEl = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        } else if (!content.contains(document.activeElement)) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };

    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      // Trả focus về nơi cũ khi đóng
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [onClose]);

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        ref={contentRef}
        className="modal-content"
        style={{ maxWidth: width }}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 className="modal-title">{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Đóng">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

// --- Chuyển đổi phân đoạn (segmented control) ---
export function Segmented({ options, value, onChange, small }) {
  return (
    <div className={`segmented${small ? " segmented-sm" : ""}`} role="group">
      {options.map((o) => (
        <button
          key={o.value}
          aria-pressed={value === o.value}
          className={value === o.value ? "on" : ""}
          onClick={() => onChange(o.value)}
          title={o.title}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// --- Chồng toast góc phải dưới ---
// Container aria-live luôn được render (kể cả khi rỗng) để screen reader
// nhận biết nội dung mới thêm vào; CSS đặt pointer-events: none cho vùng rỗng.
export function ToastStack({ toasts, onDismiss }) {
  return (
    <div className="toast-stack" aria-live="polite" role="status">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`}>
          <span className="toast-icon">
            {t.kind === "success" ? "✓" : t.kind === "error" ? "✕" : "!"}
          </span>
          <div className="toast-body">
            <div className="toast-title">{t.title}</div>
            {t.sub && <div className="toast-sub">{t.sub}</div>}
          </div>
          <button className="toast-close" onClick={() => onDismiss(t.id)} aria-label="Đóng thông báo">
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

// --- Hộp xác nhận thay cho window.confirm ---
export function ConfirmDialog({ open, title, message, confirmLabel = "Xóa", onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <Modal title={title} onClose={onCancel} width={380}>
      <p className="confirm-message">{message}</p>
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onCancel}>
          Hủy
        </button>
        <button className="btn btn-danger" onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

// --- Vòng xoay tải ---
export function Spinner({ size = 18 }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />;
}
