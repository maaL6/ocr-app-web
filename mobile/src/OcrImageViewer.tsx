import { useEffect, useState } from "react";
import { Image, View, StyleSheet, ActivityIndicator } from "react-native";
import Svg, { Polygon } from "react-native-svg";
import { OcrRecord } from "./api";
import { colors, radius } from "./theme";

type Props = {
  uri: string;
  records?: OcrRecord[];
  showBoxes?: boolean;
  highlighted?: number | null;
  onSelectBox?: (index: number | null) => void;
  containerWidth: number;
};

// Hiển thị ảnh đã OCR + vẽ bbox (toạ độ theo pixel của chính ảnh này),
// tự co theo bề rộng khung. Chạm 1 box -> highlight dòng tương ứng.
export default function OcrImageViewer({
  uri,
  records,
  showBoxes = true,
  highlighted,
  onSelectBox,
  containerWidth,
}: Props) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    setNatural(null);
    Image.getSize(
      uri,
      (w, h) => setNatural({ w, h }),
      () => setNatural(null)
    );
  }, [uri]);

  if (!natural || containerWidth <= 0) {
    return (
      <View style={[styles.loading, { width: containerWidth, height: containerWidth }]}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  const scale = containerWidth / natural.w;
  const dispW = containerWidth;
  const dispH = natural.h * scale;

  return (
    <View style={[styles.box, { width: dispW, height: dispH }]}>
      <Image source={{ uri }} style={{ width: dispW, height: dispH }} resizeMode="contain" />
      {showBoxes && records?.length ? (
        <Svg
          width={dispW}
          height={dispH}
          viewBox={`0 0 ${natural.w} ${natural.h}`}
          style={StyleSheet.absoluteFill}
        >
          {records.map((rec, i) => {
            const active = highlighted === i;
            const pts = rec.bbox.map(([x, y]) => `${x},${y}`).join(" ");
            return (
              <Polygon
                key={i}
                points={pts}
                fill={active ? "rgba(200,16,46,0.18)" : "rgba(31,164,99,0.12)"}
                stroke={active ? colors.accent : colors.box}
                strokeWidth={(active ? 4 : 2) / scale}
                onPress={() => onSelectBox?.(active ? null : i)}
              />
            );
          })}
        </Svg>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: "#000",
  },
  loading: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
  },
});
