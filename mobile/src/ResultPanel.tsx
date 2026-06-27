import { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet, ScrollView } from "react-native";
import * as Clipboard from "expo-clipboard";
import { OcrResult } from "./api";
import { colors, radius, space } from "./theme";

type Tab = "columns" | "list" | "text";

type Props = {
  result: OcrResult;
  highlighted: number | null;
  onHighlight: (i: number | null) => void;
};

export default function ResultPanel({ result, highlighted, onHighlight }: Props) {
  const [tab, setTab] = useState<Tab>("columns");
  const [copied, setCopied] = useState(false);

  // Gom record theo cột, giữ chỉ số phẳng để highlight khớp bbox.
  const byColumn = useMemo(() => {
    const m: Record<number, { text: string; idx: number; confidence: number }[]> = {};
    result.results.forEach((rec, idx) => {
      (m[rec.column] ||= []).push({ text: rec.text, idx, confidence: rec.confidence });
    });
    return m;
  }, [result]);

  async function copyAll() {
    await Clipboard.setStringAsync(result.full_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "columns", label: "Theo cột" },
    { key: "list", label: "Danh sách" },
    { key: "text", label: "Văn bản" },
  ];

  return (
    <View style={styles.wrap}>
      <View style={styles.headRow}>
        <Text style={styles.count}>
          {result.results.length} dòng · {result.columns.length} cột
          {result._ms != null ? ` · ${result._ms}ms` : ""}
        </Text>
      </View>

      <View style={styles.tabs}>
        {tabs.map((t) => (
          <Pressable
            key={t.key}
            style={[styles.tab, tab === t.key && styles.tabOn]}
            onPress={() => setTab(t.key)}
          >
            <Text style={[styles.tabText, tab === t.key && styles.tabTextOn]}>{t.label}</Text>
          </Pressable>
        ))}
      </View>

      {tab === "columns" && (
        // Cột PHẢI -> TRÁI: đảo thứ tự render; mỗi cột chữ dọc trên -> dưới.
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.colScroll}>
          <View style={styles.colRow}>
            {[...result.columns].reverse().map((col) => (
              <View key={col.index} style={styles.col}>
                <Text style={styles.colHead}>{col.index}</Text>
                <View style={styles.colText}>
                  {byColumn[col.index]?.map(({ text, idx }) => (
                    <Pressable key={idx} onPress={() => onHighlight(highlighted === idx ? null : idx)}>
                      <Text style={[styles.glyph, highlighted === idx && styles.glyphHl]}>{text}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            ))}
          </View>
        </ScrollView>
      )}

      {tab === "list" && (
        <View style={{ gap: space.xs }}>
          {result.results.map((it, i) => (
            <Pressable
              key={i}
              style={[styles.listItem, highlighted === i && styles.listItemHl]}
              onPress={() => onHighlight(highlighted === i ? null : i)}
            >
              <Text style={styles.listCol}>c{it.column}</Text>
              <Text style={styles.listText}>{it.text}</Text>
              <Text style={styles.listConf}>{(it.confidence * 100).toFixed(0)}%</Text>
            </Pressable>
          ))}
        </View>
      )}

      {tab === "text" && (
        <View>
          <Pressable style={styles.copyBtn} onPress={copyAll}>
            <Text style={styles.copyText}>{copied ? "✓ Đã copy" : "Copy toàn bộ"}</Text>
          </Pressable>
          <Text selectable style={styles.fullText}>
            {result.full_text}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.md },
  headRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  count: { fontSize: 13, color: colors.textMuted },
  tabs: {
    flexDirection: "row",
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    padding: 3,
  },
  tab: { flex: 1, paddingVertical: space.sm, borderRadius: radius.pill, alignItems: "center" },
  tabOn: { backgroundColor: colors.surface },
  tabText: { color: colors.textMuted, fontWeight: "600", fontSize: 14 },
  tabTextOn: { color: colors.primary },

  colScroll: { },
  colRow: { flexDirection: "row", gap: space.md, paddingVertical: space.sm },
  col: { alignItems: "center", gap: space.xs },
  colHead: {
    fontSize: 12,
    color: colors.textMuted,
    backgroundColor: colors.surfaceAlt,
    width: 24,
    height: 24,
    borderRadius: 12,
    textAlign: "center",
    textAlignVertical: "center",
    lineHeight: 24,
  },
  colText: { alignItems: "center" },
  glyph: { fontSize: 24, lineHeight: 30, color: colors.text, textAlign: "center" },
  glyphHl: { color: colors.accent, fontWeight: "700" },

  listItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingVertical: space.sm,
    paddingHorizontal: space.md,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt,
  },
  listItemHl: { backgroundColor: "rgba(200,16,46,0.10)" },
  listCol: { fontSize: 12, color: colors.textMuted, width: 28 },
  listText: { flex: 1, fontSize: 18, color: colors.text },
  listConf: { fontSize: 12, color: colors.textMuted },

  copyBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: space.lg,
    paddingVertical: space.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.primary,
    marginBottom: space.md,
  },
  copyText: { color: colors.primary, fontWeight: "600" },
  fullText: { fontSize: 18, lineHeight: 28, color: colors.text },
});
