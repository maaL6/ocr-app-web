"""
Gom các box OCR thành cột theo quy ước mộc bản / chữ Hán dọc:
- Cột đọc từ PHẢI sang TRÁI.
- Trong mỗi cột đọc từ TRÊN xuống DƯỚI.

Port từ assign_columns() của ocr-testing/v6_current/ocr_pipeline.py, làm việc
trên record dạng dict (không phụ thuộc dataclass).
"""

import numpy as np


def assign_columns(records: list[dict]) -> list[list[dict]]:
    """
    records: mỗi dict cần có 'cx' (center x), 'cy' (center y), 'w' (bề rộng box).
    Trả về list cột, đã sắp PHẢI->TRÁI; mỗi cột sắp TRÊN->DƯỚI.
    Gán thêm record['column'] = số thứ tự cột (1 = ngoài cùng bên phải).
    """
    if not records:
        return []

    # Phải -> trái: center_x giảm dần.
    ordered = sorted(records, key=lambda r: r["cx"], reverse=True)
    columns: list[list[dict]] = []
    current: list[dict] = []

    for rec in ordered:
        if not current:
            current.append(rec)
            continue
        cur_center = sum(r["cx"] for r in current) / len(current)
        cur_width = max(40.0, float(np.median([r["w"] for r in current])))
        rec_width = max(40.0, rec["w"])
        threshold = max(cur_width, rec_width) * 0.72
        if abs(rec["cx"] - cur_center) <= threshold:
            current.append(rec)
        else:
            columns.append(current)
            current = [rec]
    if current:
        columns.append(current)

    for index, column in enumerate(columns, start=1):
        column.sort(key=lambda r: r["cy"])  # trên -> dưới
        for rec in column:
            rec["column"] = index
    return columns
