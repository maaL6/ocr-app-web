import {
  Modal,
  View,
  Text,
  Pressable,
  StyleSheet,
  ScrollView,
  Switch,
} from "react-native";
import { OcrParams, ServerOptions, DEFAULT_PARAMS } from "./api";
import { ChipGroup, Stepper, FieldRow } from "./ui";
import { colors, radius, space, shadow } from "./theme";

type Props = {
  visible: boolean;
  params: OcrParams;
  options: ServerOptions;
  onChange: (p: OcrParams) => void;
  onClose: () => void;
};

export default function ParamsModal({ visible, params, options, onChange, onClose }: Props) {
  const set = <K extends keyof OcrParams>(k: K, v: OcrParams[K]) =>
    onChange({ ...params, [k]: v });

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.head}>
          <Text style={styles.title}>Tùy chọn tiền xử lý</Text>
          <Pressable onPress={() => onChange(DEFAULT_PARAMS)}>
            <Text style={styles.reset}>Mặc định</Text>
          </Pressable>
        </View>

        <ScrollView style={{ maxHeight: 460 }} contentContainerStyle={{ paddingBottom: space.md }}>
          <FieldRow label="Tiền xử lý mộc bản">
            <Switch
              value={params.preprocess}
              onValueChange={(v) => set("preprocess", v)}
              trackColor={{ true: colors.primary, false: colors.border }}
              thumbColor={colors.surface}
            />
          </FieldRow>

          {params.preprocess && (
            <>
              <Text style={styles.group}>Stage đưa vào OCR</Text>
              <ChipGroup options={options.stages} value={params.stage} onChange={(v) => set("stage", v)} />

              <Text style={styles.group}>Lật ảnh (flip)</Text>
              <ChipGroup
                options={options.flip_directions}
                value={params.flip}
                onChange={(v) => set("flip", v)}
              />

              <Text style={styles.group}>Khử nhiễu</Text>
              <ChipGroup
                options={options.noise_methods}
                value={params.noise_method}
                onChange={(v) => set("noise_method", v)}
              />

              <View style={styles.divider} />

              <FieldRow label="Resize width">
                <Stepper value={params.resize_width} step={100} min={0} onChange={(v) => set("resize_width", v)} />
              </FieldRow>
              <FieldRow label="Deskew range°">
                <Stepper value={params.deskew_range} step={0.5} min={0} onChange={(v) => set("deskew_range", v)} />
              </FieldRow>
              <FieldRow label="Canny low">
                <Stepper value={params.canny_low} min={0} onChange={(v) => set("canny_low", v)} />
              </FieldRow>
              <FieldRow label="Canny high">
                <Stepper value={params.canny_high} min={0} onChange={(v) => set("canny_high", v)} />
              </FieldRow>
              <FieldRow label="CLAHE clip">
                <Stepper value={params.clahe_clip} step={0.5} min={0} onChange={(v) => set("clahe_clip", v)} />
              </FieldRow>
              <FieldRow label="CLAHE tile">
                <Stepper value={params.clahe_tile} min={1} onChange={(v) => set("clahe_tile", v)} />
              </FieldRow>
            </>
          )}

          <View style={styles.divider} />
          <FieldRow label="Drop score (lọc box yếu)">
            <Stepper value={params.drop_score} step={0.05} min={0} max={1} onChange={(v) => set("drop_score", v)} />
          </FieldRow>
        </ScrollView>

        <Pressable style={styles.doneBtn} onPress={onClose}>
          <Text style={styles.doneText}>Xong</Text>
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
    ...shadow,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: space.sm,
  },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 18, fontWeight: "700", color: colors.text },
  reset: { color: colors.primary, fontWeight: "600" },
  group: { fontSize: 13, color: colors.textMuted, marginTop: space.md, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: space.sm },
  doneBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: space.md,
    alignItems: "center",
    marginTop: space.sm,
  },
  doneText: { color: colors.primaryText, fontSize: 16, fontWeight: "700" },
});
