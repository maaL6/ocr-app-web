// Tầng gọi API — mọi request tới ocr-server gom về đây.

export const DEFAULT_API = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export const FALLBACK_OPTS = {
  stages: ["warped", "deskewed", "clahe", "denoised", "flipped", "inverted"],
  noise_methods: ["gaussian", "median", "bilateral", "nlm"],
  flip_directions: ["horizontal", "vertical", "both", "none"],
};

async function jsonOrThrow(r, fallbackMsg) {
  if (!r.ok) {
    let detail = "";
    try {
      const j = await r.json();
      // FastAPI 422 trả detail là mảng lỗi validation
      detail = Array.isArray(j.detail)
        ? j.detail.map((d) => d?.msg || JSON.stringify(d)).join("; ")
        : j.detail || "";
    } catch {
      try { detail = await r.text(); } catch { /* bỏ qua */ }
    }
    const err = new Error(detail || `${fallbackMsg} (HTTP ${r.status})`);
    if (r.status === 401) err.unauthorized = true;
    throw err;
  }
  return r.json();
}

function throwIfUnauthorized(r) {
  if (r.status === 401) {
    const err = new Error("Phiên đăng nhập hết hạn");
    err.unauthorized = true;
    throw err;
  }
  return r;
}

// --- Trạng thái server ---

export async function getHealth(apiBase) {
  const r = await fetch(`${apiBase}/health`);
  const j = await r.json();
  return j.status === "ok";
}

export async function getOptions(apiBase) {
  const r = await fetch(`${apiBase}/options`);
  if (!r.ok) throw new Error("Không đọc được /options");
  return r.json();
}

// --- Tiền xử lý & OCR ---

function appendPreParams(fd, params) {
  const { preprocess, ...rest } = params;
  Object.entries(rest).forEach(([k, v]) => fd.append(k, String(v)));
}

export async function postPreprocess(apiBase, file, params) {
  const fd = new FormData();
  fd.append("file", file);
  appendPreParams(fd, params);
  const j = await jsonOrThrow(
    await fetch(`${apiBase}/preprocess`, { method: "POST", body: fd }),
    "Tiền xử lý thất bại"
  );
  return { image: j.image, meta: j.preprocess };
}

// Ảnh gửi lên luôn là ảnh cuối cùng cần OCR (đã tiền xử lý xong ở bước trước
// nếu người dùng bật) nên cả hai endpoint đều gọi với preprocess=false.
export async function postOcr(apiBase, blob, filename = "input.jpg") {
  const fd = new FormData();
  fd.append("file", blob, filename);
  fd.append("preprocess", "false");
  fd.append("return_char_confidence", "true");
  fd.append("return_char_candidates", "true");
  return jsonOrThrow(
    await fetch(`${apiBase}/ocr`, { method: "POST", body: fd }),
    "OCR thất bại"
  );
}

export async function postOcrPostprocess(apiBase, blob, filename = "input.jpg") {
  const fd = new FormData();
  fd.append("file", blob, filename);
  fd.append("preprocess", "false");
  return jsonOrThrow(
    await fetch(`${apiBase}/ocr-postprocess`, { method: "POST", body: fd }),
    "Hiệu đính AI thất bại"
  );
}

export async function dataUrlToBlob(dataUrl) {
  const res = await fetch(dataUrl);
  return res.blob();
}

// --- Auth ---

export async function postLogin(apiBase, email, password) {
  return jsonOrThrow(
    await fetch(`${apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
    "Đăng nhập thất bại"
  );
}

export async function postRegister(apiBase, form) {
  return jsonOrThrow(
    await fetch(`${apiBase}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    }),
    "Đăng ký thất bại"
  );
}

export async function postGoogleLogin(apiBase, idToken) {
  return jsonOrThrow(
    await fetch(`${apiBase}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken }),
    }),
    "Đăng nhập Google thất bại"
  );
}

// --- Tài liệu (lịch sử) ---

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getDocuments(apiBase, token) {
  const r = throwIfUnauthorized(
    await fetch(`${apiBase}/documents`, { headers: authHeaders(token) })
  );
  return jsonOrThrow(r, "Không tải được lịch sử");
}

export async function getDocument(apiBase, token, docId) {
  const r = throwIfUnauthorized(
    await fetch(`${apiBase}/documents/${docId}`, { headers: authHeaders(token) })
  );
  return jsonOrThrow(r, "Không tải được tài liệu");
}

export async function createDocument(apiBase, token, fd) {
  const r = throwIfUnauthorized(
    await fetch(`${apiBase}/documents`, {
      method: "POST",
      headers: authHeaders(token),
      body: fd,
    })
  );
  return jsonOrThrow(r, "Không thể lưu tài liệu");
}

export async function updateDocument(apiBase, token, docId, payload) {
  const r = throwIfUnauthorized(
    await fetch(`${apiBase}/documents/${docId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify(payload),
    })
  );
  return jsonOrThrow(r, "Cập nhật thất bại");
}

export async function deleteDocument(apiBase, token, docId) {
  const r = throwIfUnauthorized(
    await fetch(`${apiBase}/documents/${docId}`, {
      method: "DELETE",
      headers: authHeaders(token),
    })
  );
  if (!r.ok) throw new Error("Không thể xóa tài liệu");
}

// Ảnh lưu trong tài khoản phải kèm Authorization header → tải blob rồi tạo URL.
export async function fetchAuthenticatedImage(apiBase, token, imagePath) {
  try {
    const r = await fetch(`${apiBase}${imagePath}`, { headers: authHeaders(token) });
    if (!r.ok) throw new Error("Không thể tải ảnh");
    return URL.createObjectURL(await r.blob());
  } catch (e) {
    console.error(e);
    return null;
  }
}
