import argparse
import json
import mimetypes
import uuid
from pathlib import Path
from urllib import request


def _multipart_body(image_path: Path):
    boundary = f"----ocr-test-{uuid.uuid4().hex}"
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
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return boundary, b"".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--url", default="http://localhost:8000/ocr")
    args = parser.parse_args()

    boundary, body = _multipart_body(args.image)
    req = request.Request(
        args.url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    with request.urlopen(req, timeout=300) as res:
        payload = json.loads(res.read().decode("utf-8"))

    for item in payload.get("results", []):
        text = item["text"]
        per_char_confidences = item["per_char_confidences"]
        char_candidates = item.get("char_candidates", [])
        print("text:", text)
        print("confidence:", item["confidence"])
        print("per_char_confidences:", per_char_confidences)
        print("char_candidates:", char_candidates)
        print("len(text):", len(text))
        print("len(per_char_confidences):", len(per_char_confidences))
        print("len(char_candidates):", len(char_candidates))
        assert len(text) == len(per_char_confidences)
        assert len(text) == len(char_candidates)


if __name__ == "__main__":
    main()
