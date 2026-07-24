import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib import request, error


def _multipart_body(image_path: Path, preprocess: bool = True):
    boundary = f"----ocr-postprocess-test-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    image_bytes = image_path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            'Content-Disposition: form-data; name="file"; '
            f'filename="{image_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        image_bytes,
        f"\r\n--{boundary}\r\n".encode("utf-8"),
        'Content-Disposition: form-data; name="preprocess"\r\n\r\n'.encode("utf-8"),
        ('true' if preprocess else 'false').encode("utf-8"),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return boundary, b"".join(parts)


def send_ocr_request(url: str, image_path: Path, preprocess: bool = True):
    boundary, body = _multipart_body(image_path, preprocess=preprocess)
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with request.urlopen(req, timeout=300) as res:
        payload = json.loads(res.read().decode("utf-8"))
        headers = dict(res.headers)
        return payload, headers


def main():
    parser = argparse.ArgumentParser(description="Test OCR & SikuBERT Post-processing endpoints.")
    parser.add_argument("image", type=Path, help="Path to image file for OCR testing")
    parser.add_argument("--host", default="http://localhost:8000", help="Base URL of ocr-server")
    args = parser.parse_args()

    if not args.image.exists():
        print(f"Error: Image path '{args.image}' does not exist.")
        sys.exit(1)

    errors = []

    print("==================================================")
    print(f"Testing image: {args.image}")
    print("==================================================")

    # 1. Test raw /ocr endpoint
    raw_url = f"{args.host}/ocr"
    print(f"\n[1] Calling RAW OCR: {raw_url}")
    raw_res = None
    try:
        raw_res, raw_headers = send_ocr_request(raw_url, args.image)
        if "results" not in raw_res or "full_text" not in raw_res:
            err = f"RAW OCR response missing required keys: {list(raw_res.keys())}"
            print(f"  [ERROR] {err}")
            errors.append(err)
        else:
            print(f"-> Full text (RAW OCR):\n{raw_res.get('full_text', '')}")
    except Exception as e:
        err = f"Failed to call RAW OCR endpoint {raw_url}: {e}"
        print(f"  [ERROR] {err}")
        errors.append(err)

    # 2. Test /ocr-postprocess endpoint
    post_url = f"{args.host}/ocr-postprocess"
    print(f"\n[2] Calling OCR + SikuBERT Post-processing: {post_url}")
    try:
        post_res, post_headers = send_ocr_request(post_url, args.image)
        status_header = post_headers.get("X-Postprocess-Status", "unknown")
        fallback_reason = post_headers.get("X-Postprocess-Fallback-Reason")

        print(f"-> Postprocess Status Header: {status_header}")
        if fallback_reason:
            print(f"-> Fallback Reason Header: {fallback_reason}")

        if status_header == "fallback":
            err = f"/ocr-postprocess executed in fallback mode (reason: {fallback_reason})"
            print(f"  [WARN/ERROR] {err}")
            errors.append(err)

        if "results" not in post_res or "full_text" not in post_res:
            err = f"POST-PROCESSED response missing required keys: {list(post_res.keys())}"
            print(f"  [ERROR] {err}")
            errors.append(err)
        else:
            print(f"-> Full text (POST-PROCESSED):\n{post_res.get('full_text', '')}")
            print(f"-> Preprocess applied: {post_res.get('preprocess', {}).get('applied')}")

        # Check schema consistency with RAW OCR
        if raw_res and post_res:
            raw_root_keys = sorted(raw_res.keys())
            post_root_keys = sorted(post_res.keys())
            if raw_root_keys != post_root_keys:
                err = f"Root schema mismatch! RAW: {raw_root_keys} vs POST: {post_root_keys}"
                print(f"  [ERROR] {err}")
                errors.append(err)
            else:
                print("-> Schema check passed: Root response keys match RAW OCR.")

    except Exception as e:
        err = f"Failed to call POST-PROCESSED endpoint {post_url}: {e}"
        print(f"  [ERROR] {err}")
        errors.append(err)

    print("\n==================================================")
    if errors:
        print("[FAIL] Test failed with the following error(s):")
        for err in errors:
            print(f"  - {err}")
        print("==================================================")
        sys.exit(1)
    else:
        print("[PASS] All tests completed successfully!")
        print("==================================================")
        sys.exit(0)


if __name__ == "__main__":
    main()
