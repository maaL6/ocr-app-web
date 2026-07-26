import { useEffect, useRef, useState } from "react";

export default function Header({
  activeTab,
  onTab,
  theme,
  onToggleTheme,
  health,
  onOpenSettings,
  user,
  onOpenAuth,
  onLogout,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Đóng menu khi click ra ngoài
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [menuOpen]);

  return (
    <header className="top">
      <a
        href="/"
        className="brand"
        onClick={(e) => {
          e.preventDefault();
          onTab("ocr");
        }}
      >
        <div className="seal-logo">木</div>
        <div className="brand-text">
          <h1 className="brand-title">Mộc Bản</h1>
          <span className="brand-subtitle">Số hóa di sản Hán–Nôm</span>
        </div>
      </a>

      <nav className="nav-links" aria-label="Điều hướng chính">
        <button className={`nav-link ${activeTab === "ocr" ? "on" : ""}`} onClick={() => onTab("ocr")}>
          Nhận dạng
        </button>
        {user && (
          <button
            className={`nav-link ${activeTab === "history" ? "on" : ""}`}
            onClick={() => onTab("history")}
          >
            Lịch sử quét
          </button>
        )}
      </nav>

      <div className="header-actions">
        <a
          className="btn btn-ghost btn-app-download"
          href="https://drive.google.com/uc?export=download&id=1UASlxbXXzQ9jsxsAo_zL2qFHkvg0ouqG"
          target="_blank"
          rel="noopener noreferrer"
          title="Tải ứng dụng di động Mộc Bản OCR (qua Google Drive)"
        >
          📱 Tải app
        </a>
        <button
          className="icon-btn"
          onClick={onToggleTheme}
          title={theme === "dark" ? "Chuyển giao diện sáng" : "Chuyển giao diện tối"}
          aria-label="Đổi giao diện sáng/tối"
        >
          ◐
        </button>
        <button
          className="icon-btn settings-btn"
          onClick={onOpenSettings}
          title="Cài đặt máy chủ API"
          aria-label="Cài đặt máy chủ API"
        >
          ⚙
          <span className={`health-dot health-${health || "unknown"}`} />
        </button>

        {user ? (
          <div className="user-menu" ref={menuRef}>
            <button className="user-btn" onClick={() => setMenuOpen(!menuOpen)}>
              <span className="user-avatar">{user.fullname?.charAt(0).toUpperCase() || "U"}</span>
              <span className="user-name">{user.fullname?.split(" ").pop() || "Tài khoản"}</span>
              <span className="user-caret">▾</span>
            </button>
            {menuOpen && (
              <div className="user-dropdown">
                <div className="user-dropdown-header">
                  <div className="user-dropdown-name">{user.fullname}</div>
                  <div className="user-dropdown-email">{user.email}</div>
                </div>
                <button
                  className="user-dropdown-item"
                  onClick={() => {
                    onTab("history");
                    setMenuOpen(false);
                  }}
                >
                  Lịch sử quét
                </button>
                <button
                  className="user-dropdown-item logout"
                  onClick={() => {
                    setMenuOpen(false);
                    onLogout();
                  }}
                >
                  Đăng xuất
                </button>
              </div>
            )}
          </div>
        ) : (
          <button className="btn btn-primary" onClick={onOpenAuth}>
            Đăng nhập
          </button>
        )}
      </div>
    </header>
  );
}
