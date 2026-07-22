"""Build the compact offline UniHan feature index used by the reranker."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


UNICODE_VERSION = "17.0.0"
EXPECTED_SOURCE_SHA256 = (
    "f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e"
)
FIELDS = {
    "kSemanticVariant",
    "kZVariant",
    "kSpecializedSemanticVariant",
    "kRSUnicode",
    "kTotalStrokes",
    "kFourCornerCode",
    "kCangjie",
    "kPhonetic",
}


def build_index(source: Path) -> dict:
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            f"Unexpected UniHan source SHA-256: {source_sha256}; "
            f"expected {EXPECTED_SOURCE_SHA256}"
        )

    records: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
        for filename in sorted(archive.namelist()):
            with archive.open(filename) as input_file:
                for raw_line in input_file:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith("#"):
                        continue
                    codepoint, field, value = line.split("\t", 2)
                    if field in FIELDS:
                        records.setdefault(codepoint[2:], {})[field] = value

    return {
        "schema_version": 1,
        "unicode_version": UNICODE_VERSION,
        "source_sha256": source_sha256,
        "records": records,
    }


def write_deterministic_gzip(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8") as text_output:
                json.dump(
                    payload,
                    text_output,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Official UniHan 17.0 ZIP")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/unihan_ocr_features.json.gz"),
    )
    args = parser.parse_args()
    payload = build_index(args.source)
    write_deterministic_gzip(args.output, payload)
    print(f"Wrote {len(payload['records'])} records to {args.output}")


if __name__ == "__main__":
    main()
