# OCR Mộc Bản — App mobile (Giai đoạn 1: online)

App React Native (Expo SDK 56, TypeScript). Thin client gọi `ocr-server` (PP-OCRv6 medium):
chụp/chọn ảnh ván khắc → upload `/ocr` → hiển thị ảnh đã tiền xử lý + vẽ bbox + đọc theo cột
phải→trái (mộc bản).

> Giai đoạn 2 (sau): thêm OCR offline trên máy bằng PP-OCRv6 tiny/small (ONNX + OpenCV).

## Chạy demo (không cần Android Studio)

1. Điện thoại Android cài app **Expo Go** (Play Store). PC và điện thoại **cùng WiFi**.
2. Bật server: trong `ocr-server/` chạy `docker compose up --build`.
3. Bật bundler:
   ```bash
   cd mobile
   npx expo start
   ```
   Quét QR bằng Expo Go.
4. Trong app, bấm chip trạng thái (góc phải) → nhập **IP LAN của PC** (vd `http://192.168.1.10:8000`),
   bấm *Kiểm tra kết nối* → *Lưu*. (Trong Expo Go, `localhost` là điện thoại, không phải PC.)

> Tìm IP LAN của PC: `ipconfig` (Windows) → mục *IPv4 Address* của card WiFi.

## Cấu trúc

| File | Vai trò |
|------|---------|
| `App.tsx` | Màn chính: header trạng thái, chọn ảnh, viewer, thanh hành động, modal |
| `src/api.ts` | Client + kiểu dữ liệu khớp `ocr-server` (`/health`, `/options`, `/ocr`) |
| `src/OcrImageViewer.tsx` | Ảnh + overlay bbox (react-native-svg), co theo bề rộng |
| `src/ResultPanel.tsx` | Kết quả: tab Theo cột / Danh sách / Văn bản (+ copy) |
| `src/ParamsModal.tsx` | Bottom sheet chỉnh tham số tiền xử lý |
| `src/SettingsModal.tsx` | Cấu hình + test kết nối máy chủ |
| `src/ui.tsx`, `src/theme.ts` | Component dùng chung + bảng màu |

## Kiểm tra nhanh

```bash
npx tsc --noEmit        # typecheck
npx expo export --platform android   # thử bundle
```
