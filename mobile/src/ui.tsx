import { ReactNode } from "react";
import { Pressable, Text, View, StyleSheet, ScrollView } from "react-native";
import { colors, radius, space } from "./theme";

// Nhóm nút chọn 1-trong-nhiều (thay cho <select> trên web), cuộn ngang khi dài.
export function ChipGroup({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.chipRow}
    >
      {options.map((opt) => {
        const on = opt === value;
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            style={[styles.chip, on && styles.chipOn]}
          >
            <Text style={[styles.chipText, on && styles.chipTextOn]}>{opt}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

// Bộ tăng/giảm số có nút +/-.
export function Stepper({
  value,
  onChange,
  step = 1,
  min,
  max,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  const clamp = (v: number) => {
    if (min != null) v = Math.max(min, v);
    if (max != null) v = Math.min(max, v);
    return Math.round(v * 100) / 100;
  };
  return (
    <View style={styles.stepper}>
      <Pressable style={styles.stepBtn} onPress={() => onChange(clamp(value - step))}>
        <Text style={styles.stepSign}>−</Text>
      </Pressable>
      <Text style={styles.stepVal}>{value}</Text>
      <Pressable style={styles.stepBtn} onPress={() => onChange(clamp(value + step))}>
        <Text style={styles.stepSign}>+</Text>
      </Pressable>
    </View>
  );
}

export function FieldRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.fieldRow}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.fieldControl}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  chipRow: { gap: space.sm, paddingVertical: space.xs },
  chip: {
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text, fontSize: 14, fontWeight: "500" },
  chipTextOn: { color: colors.primaryText },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: space.sm,
  },
  stepBtn: { width: 32, height: 32, alignItems: "center", justifyContent: "center" },
  stepSign: { fontSize: 22, color: colors.primary, fontWeight: "600" },
  stepVal: { minWidth: 44, textAlign: "center", fontSize: 15, color: colors.text },
  fieldRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.md,
    paddingVertical: space.sm,
  },
  fieldLabel: { fontSize: 15, color: colors.text, fontWeight: "500", flexShrink: 1 },
  fieldControl: { flexShrink: 0 },
});
