import { useEffect, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  Pressable,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  StatusBar,
  Platform,
  Alert,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  OcrParams,
  OcrResult,
  ServerOptions,
  DEFAULT_PARAMS,
  FALLBACK_OPTIONS,
  PickedImage,
  checkHealth,
  loadOptions,
  runOcr,
} from "./src/api";
import OcrImageViewer from "./src/OcrImageViewer";
import ResultPanel from "./src/ResultPanel";
import SettingsModal from "./src/SettingsModal";
import ParamsModal from "./src/ParamsModal";
import BottomSheet from "./src/BottomSheet";
import { colors, radius, space, shadow } from "./src/theme";

const API_KEY = "@ocr/apiBase";
const DEFAULT_API = "http://192.168.1.10:8000";

type Health = "unknown" | "checking" | "ok" | "down";

export default function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState<Health>("unknown");
  const [options, setOptions] = useState<ServerOptions>(FALLBACK_OPTIONS);
  const [params, setParams] = useState<OcrParams>(DEFAULT_PARAMS);

  const [image, setImage] = useState<PickedImage | null>(null);
  const [result, setResult] = useState<OcrResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [showBoxes, setShowBoxes] = useState(true);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paramsOpen, setParamsOpen] = useState(false);
  const [stage, setStage] = useState({ w: 0, h: 0 });

  // Nạp API base đã lưu, rồi kiểm tra health + options.
  useEffect(() => {
    (async () => {
      const saved = await AsyncStorage.getItem(API_KEY);
      const base = saved || DEFAULT_API;
      setApiBase(base);
      refresh(base);
    })();
  }, []);

  async function refresh(base: string) {
    setHealth("checking");
    try {
      const ok = await checkHealth(base);
      setHealth(ok ? "ok" : "down");
      if (ok) setOptions(await loadOptions(base));
    } catch {
      setHealth("down");
    }
  }

  async function saveApiBase(base: string) {
    setApiBase(base);
    await AsyncStorage.setItem(API_KEY, base);
    refresh(base);
  }

  async function pick(from: "camera" | "library") {
    const perm =
      from === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Cần cấp quyền", "Hãy cho phép truy cập để chọn/chụp ảnh.");
      return;
    }
    const res =
      from === "camera"
        ? await ImagePicker.launchCameraAsync({ quality: 1 })
        : await ImagePicker.launchImageLibraryAsync({ quality: 1, mediaTypes: ["images"] });
    if (res.canceled || !res.assets?.length) return;
    const a = res.assets[0];
    setImage({ uri: a.uri, mimeType: a.mimeType, fileName: a.fileName ?? undefined });
    setResult(null);
    setError(null);
    setHighlighted(null);
  }

  async function doOcr() {
    if (!image) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setHighlighted(null);
    try {
      const r = await runOcr(apiBase, image, params);
      setResult(r);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  const healthColor =
    health === "ok"
      ? colors.ok
      : health === "checking"
      ? colors.warn
      : health === "down"
      ? colors.down
      : colors.textMuted;

  const viewerUri = result?.ocr_image || image?.uri;
  const imgW = stage.w - space.lg * 2;

  // 3 nấc cho sheet kết quả (peek / nửa / full), tính theo chiều cao stage.
  const snaps =
    stage.h > 0
      ? [Math.min(180, stage.h * 0.32), Math.round(stage.h * 0.52), stage.h - 6]
      : [180];

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.brand}>🪵 OCR Mộc Bản</Text>
        <Pressable style={styles.statusPill} onPress={() => setSettingsOpen(true)}>
          <View style={[styles.dot, { backgroundColor: healthColor }]} />
          <Text style={styles.statusText}>
            {health === "ok"
              ? "Đã kết nối"
              : health === "checking"
              ? "Đang kiểm tra"
              : health === "down"
              ? "Mất kết nối"
              : "Máy chủ"}
          </Text>
          <Text style={styles.gear}>⚙︎</Text>
        </Pressable>
      </View>

      {/* Stage: ảnh làm nền, sheet kết quả phủ lên */}
      <View
        style={styles.stage}
        onLayout={(e) =>
          setStage({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })
        }
      >
        {!image ? (
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📜</Text>
            <Text style={styles.emptyTitle}>Chọn ảnh mộc bản để bắt đầu</Text>
            <Text style={styles.emptyHint}>Chụp trực tiếp ván khắc hoặc chọn ảnh có sẵn.</Text>
            <View style={styles.emptyBtns}>
              <Pressable style={styles.bigBtn} onPress={() => pick("camera")}>
                <Text style={styles.bigBtnIcon}>📷</Text>
                <Text style={styles.bigBtnText}>Chụp ảnh</Text>
              </Pressable>
              <Pressable style={[styles.bigBtn, styles.bigBtnAlt]} onPress={() => pick("library")}>
                <Text style={styles.bigBtnIcon}>🖼️</Text>
                <Text style={[styles.bigBtnText, { color: colors.primary }]}>Thư viện</Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <>
            {/* Lớp ảnh (cuộn dọc nếu ảnh cao) */}
            <ScrollView
              style={StyleSheet.absoluteFill}
              contentContainerStyle={styles.imageScroll}
              showsVerticalScrollIndicator={false}
            >
              {viewerUri && imgW > 0 && (
                <OcrImageViewer
                  uri={viewerUri}
                  records={result?.results}
                  showBoxes={showBoxes}
                  highlighted={highlighted}
                  onSelectBox={setHighlighted}
                  containerWidth={imgW}
                />
              )}
            </ScrollView>

            {/* Control nổi góc phải */}
            <View style={styles.floatControls}>
              <Pressable style={styles.floatBtn} onPress={() => pick("library")}>
                <Text style={styles.floatText}>Đổi ảnh</Text>
              </Pressable>
              {result && (
                <Pressable style={styles.floatBtn} onPress={() => setShowBoxes((s) => !s)}>
                  <Text style={styles.floatText}>{showBoxes ? "Ẩn khung" : "Hiện khung"}</Text>
                </Pressable>
              )}
            </View>

            {/* Báo lỗi nổi trên cùng */}
            {error && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>⚠️ {error}</Text>
              </View>
            )}

            {/* Sheet kết quả */}
            {result && stage.h > 0 && (
              <BottomSheet stageHeight={stage.h} snaps={snaps} initialIndex={1}>
                <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: space.xl }}>
                  <ResultPanel result={result} highlighted={highlighted} onHighlight={setHighlighted} />
                </ScrollView>
              </BottomSheet>
            )}
          </>
        )}
      </View>

      {/* Thanh hành động dưới cùng */}
      {image && (
        <View style={styles.bottomBar}>
          <Pressable style={styles.optBtn} onPress={() => setParamsOpen(true)}>
            <Text style={styles.optText}>⚙︎ Tùy chọn</Text>
          </Pressable>
          <Pressable
            style={[styles.runBtn, loading && styles.runBtnDisabled]}
            onPress={doOcr}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color={colors.primaryText} />
            ) : (
              <Text style={styles.runText}>{result ? "Chạy lại OCR" : "Chạy OCR"}</Text>
            )}
          </Pressable>
        </View>
      )}

      <SettingsModal
        visible={settingsOpen}
        apiBase={apiBase}
        onClose={() => setSettingsOpen(false)}
        onSave={saveApiBase}
      />
      <ParamsModal
        visible={paramsOpen}
        params={params}
        options={options}
        onChange={setParams}
        onClose={() => setParamsOpen(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bg,
    paddingTop: Platform.OS === "android" ? StatusBar.currentHeight ?? 0 : 0,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  brand: { fontSize: 20, fontWeight: "800", color: colors.text },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    backgroundColor: colors.surface,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 13, color: colors.text, fontWeight: "500" },
  gear: { fontSize: 14, color: colors.textMuted },

  stage: { flex: 1, overflow: "hidden" },
  imageScroll: { padding: space.lg, alignItems: "center" },

  floatControls: {
    position: "absolute",
    top: space.md,
    right: space.md,
    gap: space.sm,
    alignItems: "flex-end",
  },
  floatBtn: {
    backgroundColor: "rgba(255,255,255,0.92)",
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow,
  },
  floatText: { color: colors.primary, fontWeight: "600", fontSize: 13 },

  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: space.md, padding: space.xl },
  emptyIcon: { fontSize: 64 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: colors.text, textAlign: "center" },
  emptyHint: { fontSize: 14, color: colors.textMuted, textAlign: "center" },
  emptyBtns: { flexDirection: "row", gap: space.md, marginTop: space.lg },
  bigBtn: {
    alignItems: "center",
    gap: space.xs,
    backgroundColor: colors.primary,
    paddingHorizontal: space.xl,
    paddingVertical: space.lg,
    borderRadius: radius.lg,
    minWidth: 130,
    ...shadow,
  },
  bigBtnAlt: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.primary },
  bigBtnIcon: { fontSize: 28 },
  bigBtnText: { fontSize: 16, fontWeight: "700", color: colors.primaryText },

  errorBox: {
    position: "absolute",
    top: space.md,
    left: space.md,
    right: space.md,
    backgroundColor: "#fff",
    borderRadius: radius.md,
    padding: space.md,
    borderWidth: 1,
    borderColor: "rgba(200,16,46,0.4)",
    ...shadow,
  },
  errorText: { color: colors.down, fontSize: 14 },

  bottomBar: {
    flexDirection: "row",
    gap: space.md,
    padding: space.lg,
    paddingBottom: space.xl,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  optBtn: {
    paddingHorizontal: space.lg,
    justifyContent: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
  },
  optText: { color: colors.text, fontWeight: "600" },
  runBtn: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: space.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  runBtnDisabled: { opacity: 0.6 },
  runText: { color: colors.primaryText, fontSize: 16, fontWeight: "700" },
});
