import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import List, Optional

import pypdfium2 as pdfium


MAX_PDFIUM_BITMAP_DIMENSION = 32767


def claim_spool_pdf(spool_path: Path) -> Optional[Path]:
    backoff = 0.1
    last_size = -1
    stable_count = 0
    for _ in range(60):
        if not spool_path.exists():
            return None
        try:
            size = spool_path.stat().st_size
            if size > 0:
                with open(spool_path, "rb+") as file:
                    if file.read(5) == b"%PDF-":
                        if size == last_size:
                            stable_count += 1
                            if stable_count >= 2:
                                job_pdf = spool_path.parent / f"print_to_png_job_{uuid.uuid4().hex[:8]}.pdf"
                                shutil.copy2(spool_path, job_pdf)
                                file.seek(0)
                                file.truncate(0)
                                break
                        else:
                            last_size = size
                            stable_count = 1
        except (PermissionError, OSError):
            stable_count = 0
        time.sleep(backoff)
        backoff = min(backoff * 1.25, 0.8)
    else:
        return None

    try:
        spool_path.unlink(missing_ok=True)
    except Exception:
        pass
    return job_pdf


def render_pdf_to_target_png(
    job_pdf: Path, target_png: Path, dpi: int, logger: logging.Logger
) -> List[Path]:
    scale = dpi / 72.0
    stem = target_png.stem
    target_png.parent.mkdir(parents=True, exist_ok=True)
    output_files: List[Path] = []
    pdf_doc = pdfium.PdfDocument(str(job_pdf))
    num_pages = len(pdf_doc)
    logger.info(f"開始直接輸出 PNG ({num_pages} 頁, {dpi} DPI) -> {target_png}")
    try:
        for page_index in range(num_pages):
            page = pdf_doc[page_index]
            try:
                width_pt, height_pt = page.get_size()
                width_px = round(width_pt * scale)
                height_px = round(height_pt * scale)
                if max(width_px, height_px) > MAX_PDFIUM_BITMAP_DIMENSION:
                    raise ValueError(
                        f"{dpi} DPI 會產生 {width_px:,} x {height_px:,} 像素，"
                        f"超過 PDFium 單一位圖上限 {MAX_PDFIUM_BITMAP_DIMENSION:,} 像素；"
                        "請選擇較低 DPI 或較小的頁面尺寸。"
                    )
                logger.info(
                    f"正在渲染第 {page_index + 1}/{num_pages} 頁 "
                    f"({width_px:,} x {height_px:,} 像素, {dpi} DPI)"
                )
                image = page.render(scale=scale, rotation=0).to_pil()
                out_path = (
                    target_png.parent / f"{stem}.png"
                    if num_pages == 1
                    else target_png.parent / f"{stem}_p{page_index + 1}.png"
                )
                image.save(str(out_path), format="PNG", dpi=(dpi, dpi))
                output_files.append(out_path)
                logger.info(f"第 {page_index + 1}/{num_pages} 頁已完成：{out_path}")
            finally:
                page.close()
    finally:
        pdf_doc.close()
    return output_files
