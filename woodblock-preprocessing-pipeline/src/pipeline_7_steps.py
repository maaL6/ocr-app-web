"""
Woodblock Image Preprocessing Pipeline
======================================

Pipeline:
    corners -> warp -> deskew -> clahe -> denoise -> flipped -> inverted

Default input:
    data/input/

Default output:
    data/output/<image_name>/
        01_corners.jpg
        02_warped.jpg
        03_deskewed.jpg
        04_clahe.jpg
        05_denoised.jpg
        06_flipped.jpg
        07_inverted.jpg

Run from project root:
    python src/pipeline_7_steps.py
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import cv2

# Allow imports from src/modules when this script is executed directly.
sys.path.insert(0, str(Path(__file__).parent))

from modules.perspective_correction import auto_perspective_correction, draw_corners
from modules.deskew import deskew
from modules.clahe import apply_clahe
from modules.noise_reduction import reduce_noise
from modules.mirror_flip import mirror_flip
from modules.resize import resize_by_width


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run 7-step preprocessing pipeline for woodblock images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--input", default="data/input", help="Input image folder.")
    parser.add_argument("--output", default="data/output", help="Output folder.")
    parser.add_argument(
        "--resize",
        type=int,
        default=1600,
        help="Resize image width before processing. Use 0 to disable.",
    )
    parser.add_argument("--recursive", action="store_true", help="Read images in subfolders.")
    parser.add_argument("--clean", action="store_true", help="Remove output folder before running.")

    # Perspective correction
    parser.add_argument("--canny-low", type=int, default=30)
    parser.add_argument("--canny-high", type=int, default=120)

    # Deskew
    parser.add_argument("--deskew-range", type=float, default=15.0)

    # CLAHE
    parser.add_argument("--clahe-clip", type=float, default=3.0)
    parser.add_argument("--clahe-tile", type=int, default=8)

    # Denoise
    parser.add_argument(
        "--noise-method",
        choices=["gaussian", "median", "bilateral", "nlm"],
        default="bilateral",
    )

    # Flip
    parser.add_argument(
        "--flip",
        choices=["horizontal", "vertical", "both", "none"],
        default="horizontal",
        help="Flip direction. horizontal is recommended for woodblock images.",
    )

    return parser.parse_args()


def find_images(input_dir: Path, recursive: bool):
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in input_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def safe_stem(path: Path) -> str:
    return path.stem.replace(" ", "_")


def process_one_image(img_path: Path, output_root: Path, args) -> dict:
    log = {
        "file": img_path.name,
        "status": "FAIL",
        "strategy": "",
        "auto_detected": False,
        "skew_angle": 0.0,
        "input_shape": "",
        "output_shape": "",
        "time_s": 0.0,
        "error": "",
    }

    start_time = time.time()

    try:
        image = cv2.imread(str(img_path))
        if image is None:
            log["error"] = "cv2.imread returned None"
            return log

        h, w = image.shape[:2]
        log["input_shape"] = f"{w}x{h}"

        if args.resize > 0 and image.shape[1] > args.resize:
            image = resize_by_width(image, args.resize)

        target_dir = output_root / safe_stem(img_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Detect corners + 2. Warp
        warped, corners, strategy = auto_perspective_correction(
            image,
            canny_low=args.canny_low,
            canny_high=args.canny_high,
            return_strategy=True,
        )

        if warped is None:
            warped = image.copy()
            log["error"] = "Perspective failed; used original image."
        else:
            log["auto_detected"] = True
            log["strategy"] = strategy
            corners_debug = draw_corners(image, corners)
            cv2.imwrite(str(target_dir / "01_corners.jpg"), corners_debug)

        cv2.imwrite(str(target_dir / "02_warped.jpg"), warped)
        current = warped

        # 3. Deskew
        current, angle = deskew(
            current,
            angle_range=args.deskew_range,
            return_angle=True,
        )
        log["skew_angle"] = round(angle, 3)
        cv2.imwrite(str(target_dir / "03_deskewed.jpg"), current)

        # 4. CLAHE
        current = apply_clahe(
            current,
            clip_limit=args.clahe_clip,
            tile_grid_size=args.clahe_tile,
        )
        cv2.imwrite(str(target_dir / "04_clahe.jpg"), current)

        # 5. Denoise
        current = reduce_noise(current, method=args.noise_method)
        cv2.imwrite(str(target_dir / "05_denoised.jpg"), current)

        # 6. Flipped
        if args.flip != "none":
            current = mirror_flip(current, direction=args.flip)
        cv2.imwrite(str(target_dir / "06_flipped.jpg"), current)

        # 7. Inverted
        current = cv2.bitwise_not(current)
        cv2.imwrite(str(target_dir / "07_inverted.jpg"), current)

        h2, w2 = current.shape[:2]
        log["output_shape"] = f"{w2}x{h2}"
        log["status"] = "OK"

    except Exception as exc:
        log["error"] = f"{type(exc).__name__}: {exc}"

    log["time_s"] = round(time.time() - start_time, 3)
    return log


def main():
    args = parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.exists():
        print(f"[ERROR] Input folder does not exist: {input_dir}")
        sys.exit(1)

    if args.clean and output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
        print(f"[CLEAN] Removed old output folder: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    images = find_images(input_dir, args.recursive)
    if not images:
        print(f"[ERROR] No images found in: {input_dir}")
        print(f"Supported formats: {sorted(IMAGE_EXTS)}")
        sys.exit(1)

    print(f"Input : {input_dir}")
    print(f"Output: {output_dir}")
    print("Pipeline: corners -> warp -> deskew -> clahe -> denoise -> flipped -> inverted")
    print(f"Found {len(images)} image(s).")
    print("-" * 70)

    logs = []
    ok_count = 0
    fail_count = 0
    auto_count = 0

    for idx, img_path in enumerate(images, start=1):
        print(f"[{idx:3d}/{len(images)}] {img_path.name}", end=" ... ", flush=True)
        log = process_one_image(img_path, output_dir, args)
        logs.append(log)

        if log["status"] == "OK":
            ok_count += 1
            if log["auto_detected"]:
                auto_count += 1
                strategy_text = log["strategy"]
            else:
                strategy_text = "original"

            print(
                f"OK (strategy={strategy_text}, "
                f"skew={log['skew_angle']:+.2f}°, "
                f"time={log['time_s']}s)"
            )
        else:
            fail_count += 1
            print(f"FAIL: {log['error']}")

    log_path = output_dir / "run_log.csv"
    with open(log_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=logs[0].keys())
        writer.writeheader()
        writer.writerows(logs)

    print("\n" + "=" * 70)
    print(f"Total images: {len(images)}")
    print(f"OK: {ok_count}")
    print(f"FAIL: {fail_count}")
    print(f"Auto-detected corners: {auto_count}")
    print(f"Log file: {log_path}")


if __name__ == "__main__":
    main()
