// Client gọi OCR server (FastAPI PP-OCRv6). Giai đoạn 1: chỉ online.
// Hợp đồng API khớp ocr-server/app/main.py.
import { File, UploadType } from "expo-file-system";

export type Bbox = [number, number][];

export type OcrRecord = {
  text: string;
  confidence: number;
  bbox: Bbox;
  column: number;
};

export type OcrColumn = {
  index: number;
  text: string;
  avg_score: number;
};

export type PreprocessMeta = {
  applied: boolean;
  stage?: string;
  strategy?: string;
  auto_detected?: boolean;
  skew_angle?: number;
  input_shape?: string;
  output_shape?: string;
};

export type OcrResult = {
  results: OcrRecord[];
  columns: OcrColumn[];
  full_text: string;
  ocr_image: string; // data:image/jpeg;base64,...
  preprocess: PreprocessMeta;
  _ms?: number;
};

export type ServerOptions = {
  stages: string[];
  noise_methods: string[];
  flip_directions: string[];
};

export const FALLBACK_OPTIONS: ServerOptions = {
  stages: ["warped", "deskewed", "clahe", "denoised", "flipped", "inverted"],
  noise_methods: ["gaussian", "median", "bilateral", "nlm"],
  flip_directions: ["horizontal", "vertical", "both", "none"],
};

export type OcrParams = {
  preprocess: boolean;
  stage: string;
  flip: string;
  noise_method: string;
  resize_width: number;
  canny_low: number;
  canny_high: number;
  deskew_range: number;
  clahe_clip: number;
  clahe_tile: number;
  drop_score: number;
};

export const DEFAULT_PARAMS: OcrParams = {
  preprocess: true,
  stage: "flipped",
  flip: "horizontal",
  noise_method: "bilateral",
  resize_width: 1600,
  canny_low: 30,
  canny_high: 120,
  deskew_range: 15,
  clahe_clip: 3,
  clahe_tile: 8,
  drop_score: 0.3,
};

function trimBase(base: string) {
  return base.replace(/\/+$/, "");
}

export async function checkHealth(base: string): Promise<boolean> {
  const r = await fetch(`${trimBase(base)}/health`, { method: "GET" });
  if (!r.ok) return false;
  const j = await r.json();
  return j?.status === "ok";
}

export async function loadOptions(base: string): Promise<ServerOptions> {
  try {
    const r = await fetch(`${trimBase(base)}/options`);
    if (r.ok) return (await r.json()) as ServerOptions;
  } catch {
    /* dùng fallback */
  }
  return FALLBACK_OPTIONS;
}

export type PickedImage = { uri: string; mimeType?: string; fileName?: string };

// Gửi 1 request /ocr: server tự tiền xử lý (nếu bật) rồi OCR, trả ocr_image + bbox.
//
// Dùng expo-file-system File.upload (multipart native) thay cho fetch+FormData:
// global fetch của Expo SDK 56 là expo/fetch, KHÔNG nhận file dạng {uri,name,type}
// của React Native (báo "Unsupported FormDataPart implementation"). File.upload
// cũng cho set mimeType -> server qua được check content_type phải là image/*.
export async function runOcr(
  base: string,
  image: PickedImage,
  params: OcrParams
): Promise<OcrResult> {
  // Mọi field form của /ocr đều là chuỗi.
  const parameters: Record<string, string> = {
    preprocess: String(params.preprocess),
    stage: params.stage,
    flip: params.flip,
    noise_method: params.noise_method,
    resize_width: String(params.resize_width),
    canny_low: String(params.canny_low),
    canny_high: String(params.canny_high),
    deskew_range: String(params.deskew_range),
    clahe_clip: String(params.clahe_clip),
    clahe_tile: String(params.clahe_tile),
    drop_score: String(params.drop_score),
  };

  const t0 = Date.now();
  const res = await new File(image.uri).upload(`${trimBase(base)}/ocr`, {
    httpMethod: "POST",
    uploadType: UploadType.MULTIPART,
    fieldName: "file",
    mimeType: image.mimeType || "image/jpeg",
    parameters,
  });
  if (res.status < 200 || res.status >= 300) {
    throw new Error(`HTTP ${res.status}: ${res.body || ""}`);
  }
  const j = normalizeResult(JSON.parse(res.body));
  j._ms = Date.now() - t0;
  return j;
}

// Server mới trả sẵn `columns` + `column`. Nhưng để app không crash với server cũ
// (hoặc response thiếu field), tự suy ra cho đủ: mỗi result luôn có `column`,
// và luôn có mảng `columns` (gom theo `column`, giữ thứ tự xuất hiện).
export function normalizeResult(raw: any): OcrResult {
  const results: OcrRecord[] = (Array.isArray(raw?.results) ? raw.results : []).map(
    (r: any) => ({
      text: String(r?.text ?? ""),
      confidence: Number(r?.confidence ?? 0),
      bbox: Array.isArray(r?.bbox) ? r.bbox : [],
      column: Number.isFinite(r?.column) ? r.column : 1,
    })
  );

  let columns: OcrColumn[] = Array.isArray(raw?.columns) ? raw.columns : [];
  if (!columns.length && results.length) {
    const order: number[] = [];
    const groups: Record<number, OcrRecord[]> = {};
    for (const r of results) {
      if (!(r.column in groups)) {
        groups[r.column] = [];
        order.push(r.column);
      }
      groups[r.column].push(r);
    }
    columns = order.map((col) => {
      const g = groups[col];
      return {
        index: col,
        text: g.map((r) => r.text).join(""),
        avg_score: g.reduce((s, r) => s + r.confidence, 0) / g.length,
      };
    });
  }

  return {
    results,
    columns,
    full_text: typeof raw?.full_text === "string" ? raw.full_text : "",
    ocr_image: typeof raw?.ocr_image === "string" ? raw.ocr_image : "",
    preprocess: raw?.preprocess ?? { applied: false },
  };
}
