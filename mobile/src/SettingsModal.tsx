import { useState } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { checkHealth } from "./api";
import { colors, radius, space, shadow } from "./theme";

type Props = {
  visible: boolean;
  apiBase: string;
  onClose: () => void;
  onSave: (base: string) => void;
};

export default function SettingsModal({ visible, apiBase, onClose, onSave }: Props) {
  const [draft, setDraft] = useState(apiBase);
  const [status, setStatus] = useState<"idle" | "checking" | "ok" | "down">("idle");

  async function test() {
    setStatus("checking");
    try {
      setStatus((await checkHealth(draft)) ? "ok" : "down");
    } catch {
      setStatus("down");
    }
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <Text style={styles.title}>Máy chủ OCR</Text>
        <Text style={styles.hint}>
          Nhập IP LAN của máy chạy server (vd http://192.168.1.10:8000). Trong Expo Go,
          “localhost” là điện thoại — không phải máy tính.
        </Text>

        <TextInput
          value={draft}
          onChangeText={(t) => {
            setDraft(t);
            setStatus("idle");
          }}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="http://192.168.1.10:8000"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
        />

        <View style={styles.row}>
          <Pressable style={styles.testBtn} onPress={test}>
            {status === "checking" ? (
              <ActivityIndicator color={colors.primary} size="small" />
            ) : (
              <Text style={styles.testText}>Kiểm tra kết nối</Text>
            )}
          </Pressable>
          {status === "ok" && <Text style={[styles.badge, { color: colors.ok }]}>● Kết nối OK</Text>}
          {status === "down" && (
            <Text style={[styles.badge, { color: colors.down }]}>● Không kết nối được</Text>
          )}
        </View>

        <Pressable
          style={styles.saveBtn}
          onPress={() => {
            onSave(draft.trim());
            onClose();
          }}
        >
          <Text style={styles.saveText}>Lưu</Text>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)" },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: space.lg,
    paddingBottom: space.xl,
    gap: space.md,
    ...shadow,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: space.xs,
  },
  title: { fontSize: 18, fontWeight: "700", color: colors.text },
  hint: { fontSize: 13, color: colors.textMuted, lineHeight: 18 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.md,
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.surfaceAlt,
  },
  row: { flexDirection: "row", alignItems: "center", gap: space.md },
  testBtn: {
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  testText: { color: colors.primary, fontWeight: "600" },
  badge: { fontSize: 13, fontWeight: "600" },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: space.md,
    alignItems: "center",
    marginTop: space.sm,
  },
  saveText: { color: colors.primaryText, fontSize: 16, fontWeight: "700" },
});
