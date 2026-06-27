import { ReactNode, useEffect, useRef } from "react";
import { Animated, PanResponder, StyleSheet, View } from "react-native";
import { colors, radius, shadow, space } from "./theme";

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

type Props = {
  stageHeight: number; // chiều cao vùng chứa (giữa header và bottom bar)
  snaps: number[]; // các mức chiều cao HIỆN của sheet, tăng dần (peek -> full)
  initialIndex?: number;
  header?: ReactNode; // vùng tay cầm (nhận thao tác kéo)
  children: ReactNode; // nội dung cuộn
};

// Sheet kéo 3 nấc tự viết (Animated + PanResponder) — không cần reanimated/gesture-handler.
// Sheet cao = mức full; dịch xuống bằng translateY để lộ đúng mức snap hiện tại.
export default function BottomSheet({ stageHeight, snaps, initialIndex = 0, header, children }: Props) {
  const maxH = snaps[snaps.length - 1];
  const minVisible = snaps[0];
  const current = useRef(snaps[initialIndex] ?? snaps[0]);
  const translateY = useRef(new Animated.Value(maxH - current.current)).current;

  // stageHeight đổi (xoay máy) -> snap lại cho khớp.
  useEffect(() => {
    snapTo(current.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [maxH]);

  function snapTo(visible: number) {
    current.current = visible;
    Animated.spring(translateY, {
      toValue: maxH - visible,
      useNativeDriver: true,
      bounciness: 2,
      speed: 16,
    }).start();
  }

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
      onPanResponderMove: (_, g) => {
        const ty = clamp(maxH - current.current + g.dy, 0, maxH - minVisible);
        translateY.setValue(ty);
      },
      onPanResponderRelease: (_, g) => {
        // ưu tiên hướng vung mạnh; nếu không thì bám mức gần nhất.
        let target = clamp(current.current - g.dy, minVisible, maxH);
        if (g.vy < -0.5) target = maxH; // vung lên -> mở full
        else if (g.vy > 0.5) target = minVisible; // vung xuống -> peek
        const nearest = snaps.reduce((a, b) =>
          Math.abs(b - target) < Math.abs(a - target) ? b : a
        );
        snapTo(nearest);
      },
    })
  ).current;

  return (
    <Animated.View
      style={[styles.sheet, { height: maxH, transform: [{ translateY }] }]}
    >
      <View {...pan.panHandlers} style={styles.grab}>
        <View style={styles.handle} />
        {header}
      </View>
      <View style={styles.body}>{children}</View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    ...shadow,
    shadowOffset: { width: 0, height: -4 },
  },
  grab: {
    paddingTop: space.sm,
    paddingHorizontal: space.lg,
    paddingBottom: space.sm,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: space.sm,
  },
  body: { flex: 1, paddingHorizontal: space.lg },
});
