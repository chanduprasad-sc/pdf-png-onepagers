from pathlib import Path
from datetime import datetime
import gc
import os
import re
import zipfile
import time
import tempfile
import shutil

import fitz  # PyMuPDF
import streamlit as st

# Keep each Tesseract subprocess small enough for Streamlit Community Cloud.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DRIVE_ROOT_FOLDER_ID = "1R_fjJmLYUqLPsphGIy1saPo9vP9o7Cp4"
DRIVE_ROOT_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    f"{DRIVE_ROOT_FOLDER_ID}"
)
APP_STATE_VERSION = 3

st.set_page_config(
    page_title="PDF Page Exporter",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        :root {
            --app-bg: oklch(0.975 0 0);
            --surface: oklch(1 0 0);
            --surface-subtle: oklch(0.955 0.008 140);
            --surface-raised: oklch(0.99 0.004 140);
            --ink: oklch(0.19 0.025 140);
            --muted: oklch(0.46 0.02 140);
            --line: oklch(0.88 0.012 140);
            --line-strong: oklch(0.78 0.025 140);
            --primary: oklch(0.35 0.11 140);
            --primary-hover: oklch(0.30 0.105 140);
            --accent: oklch(0.58 0.13 235);
            --focus: var(--accent);
            --radius-sm: 0.65rem;
            --radius-md: 0.9rem;
            --shadow-sm: 0 0.3rem 1.1rem oklch(0.19 0.025 140 / 0.055);
        }

        html { color-scheme: light; }
        .stApp { background: var(--app-bg); color: var(--ink); }
        .block-container {
            max-width: 1080px;
            padding-top: 3rem;
            padding-bottom: 5rem;
        }
        header[data-testid="stHeader"] { background: transparent; }

        .app-hero {
            display: flex;
            align-items: flex-start;
            gap: 1.15rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--line);
        }
        .app-mark {
            display: grid;
            place-items: center;
            width: 3.25rem;
            height: 3.25rem;
            flex: 0 0 auto;
            border-radius: var(--radius-md);
            background: var(--primary);
            color: oklch(1 0 0);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.04em;
            box-shadow: 0 0.5rem 1.5rem oklch(0.35 0.11 140 / 0.16);
        }
        .app-hero-copy { flex: 1; min-width: 0; }
        .app-hero h1 {
            margin: 0 0 0.25rem;
            color: var(--ink);
            font-size: 2rem;
            line-height: 1.15;
            letter-spacing: -0.025em;
            text-wrap: balance;
        }
        .app-hero p {
            max-width: 68ch;
            margin: 0;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.55;
            text-wrap: pretty;
        }
        .hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.8rem;
        }
        .hero-meta span {
            display: inline-flex;
            align-items: center;
            min-height: 1.8rem;
            padding: 0.25rem 0.65rem;
            border: 1px solid var(--line);
            border-radius: 999px;
            background: var(--surface);
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 600;
        }
        .workflow-note {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin: 0 0 2.35rem;
            color: var(--muted);
            font-size: 0.875rem;
        }
        .workflow-note span {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            min-height: 2.15rem;
            padding: 0.35rem 0.7rem 0.35rem 0.4rem;
            border-radius: 999px;
            background: var(--surface-subtle);
            white-space: nowrap;
        }
        .workflow-note strong {
            display: grid;
            place-items: center;
            width: 1.45rem;
            height: 1.45rem;
            border-radius: 999px;
            background: var(--surface);
            color: var(--primary);
            box-shadow: 0 0 0 1px var(--line);
            font-size: 0.75rem;
        }
        .conversion-note {
            margin: 0.75rem 0 1rem;
            padding: 0.85rem 1rem;
            border-left: 3px solid var(--primary);
            border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
            background: var(--surface-subtle);
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.55;
        }
        .conversion-note strong { color: var(--ink); }

        h2, h3 { color: var(--ink); letter-spacing: -0.015em; }
        div[data-testid="stFileUploaderDropzone"] {
            min-height: 12rem;
            border: 1.5px dashed var(--line) !important;
            border-radius: var(--radius-md);
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: var(--shadow-sm);
            transition: border-color 180ms ease-out, background 180ms ease-out,
                        box-shadow 180ms ease-out;
        }
        div[data-testid="stFileUploaderDropzone"]:hover {
            border-color: var(--primary) !important;
            background: var(--surface-subtle) !important;
            box-shadow: 0 0 0 3px oklch(0.68 0.13 140 / 0.12);
        }
        div[data-testid="stFileUploaderDropzone"] button {
            border-color: var(--primary) !important;
            background: var(--primary) !important;
            color: oklch(1 0 0) !important;
            font-weight: 650;
        }
        div[data-testid="stFileUploaderDropzone"] button:hover {
            border-color: var(--primary-hover) !important;
            background: var(--primary-hover) !important;
        }
        div[data-testid="stFileUploaderDropzone"] button p,
        div[data-testid="stFileUploaderDropzone"] button span {
            color: oklch(1 0 0) !important;
        }
        div[data-testid="stFileUploaderDropzone"] button svg {
            fill: oklch(1 0 0) !important;
            color: oklch(1 0 0) !important;
        }
        div[data-testid="stFileUploaderDropzone"] small,
        div[data-testid="stFileUploaderDropzone"] > div > span {
            color: var(--muted) !important;
        }
        div[data-testid="stFileUploaderFile"] {
            border-radius: var(--radius-sm);
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        div[data-testid="stSlider"] label,
        div[data-testid="stSlider"] p {
            color: var(--ink) !important;
        }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stDownloadButton"] > button {
            min-height: 2.8rem;
            border: 1px solid var(--primary);
            border-radius: var(--radius-sm);
            background: var(--primary);
            color: oklch(1 0 0);
            font-weight: 650;
            transition: background 180ms ease-out, border-color 180ms ease-out,
                        transform 180ms ease-out;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            border-color: var(--primary-hover);
            background: var(--primary-hover);
            color: oklch(1 0 0);
            transform: translateY(-1px);
        }
        div[data-testid="stButton"] > button:focus-visible,
        div[data-testid="stDownloadButton"] > button:focus-visible {
            outline: 3px solid oklch(0.68 0.13 140 / 0.35);
            outline-offset: 2px;
        }
        div[data-testid="stButton"] > button:disabled {
            border-color: var(--line);
            background: oklch(0.89 0.008 140);
            color: oklch(0.47 0.015 140);
        }
        div[data-testid="stButton"] > button:not([kind="primary"]),
        div[data-testid="stPopover"] > button {
            min-height: 2.8rem;
            border-color: var(--line-strong);
            border-radius: var(--radius-sm);
            background: var(--surface);
            color: var(--ink);
            transition: border-color 180ms ease-out, background 180ms ease-out,
                        transform 180ms ease-out;
        }
        div[data-testid="stButton"] > button:not([kind="primary"]):hover,
        div[data-testid="stPopover"] > button:hover {
            border-color: var(--primary);
            background: var(--surface-subtle);
            color: var(--primary);
            transform: translateY(-1px);
        }
        div[data-baseweb="select"] > div,
        div[data-testid="stTextInput"] input {
            border-radius: var(--radius-sm);
            border-color: var(--line-strong);
            background: var(--surface);
        }
        div[data-baseweb="select"] > div:focus-within,
        div[data-testid="stTextInput"] input:focus {
            border-color: var(--focus);
            box-shadow: 0 0 0 3px oklch(0.58 0.13 235 / 0.16);
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line) !important;
            border-radius: var(--radius-md) !important;
            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }
        div[data-testid="stAlert"] { border-radius: var(--radius-sm); }
        div[data-testid="stExpander"] {
            border-color: var(--line);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }
        div[data-testid="stImage"] img { border-radius: 0.55rem; }
        .removed-image-slot {
            display: grid;
            place-items: center;
            width: 100%;
            min-height: 11rem;
            aspect-ratio: 0.707;
            border: 1px dashed var(--line);
            border-radius: 0.55rem;
            background: var(--surface-subtle);
            color: var(--muted);
            text-align: center;
        }
        .removed-image-slot strong {
            display: block;
            margin-bottom: 0.25rem;
            color: var(--ink);
        }
        .result-meta { color: var(--muted); font-size: 0.9rem; }
        .result-counts {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
        }
        .result-counts span {
            padding: 0.3rem 0.6rem;
            border: 1px solid var(--line);
            border-radius: 999px;
            background: var(--surface-raised);
        }
        .result-counts strong { color: var(--ink); font-weight: 700; }
        .package-note {
            margin: 0.6rem 0 0;
            color: var(--muted);
            font-size: 0.82rem;
        }
        .package-note strong { color: var(--primary); }

        @media (max-width: 640px) {
            .block-container { padding-top: 2rem; }
            .app-hero { gap: 0.8rem; }
            .app-hero h1 { font-size: 1.65rem; }
            .app-mark { width: 2.8rem; height: 2.8rem; }
            .workflow-note { display: grid; }
            .workflow-note span { white-space: normal; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_name(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:120] if name else 'page'


def safe_pdf_name(original_name: str) -> str:
    """Preserve the uploaded PDF name while keeping it filesystem-safe."""
    stem = safe_name(Path(original_name).stem)[:112]
    return f"{stem}.pdf"


def cleanup_batch_temp_dir(path_value: str | None):
    """Remove only a temp directory created by this app."""
    if not path_value:
        return
    path = Path(path_value).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if path.parent == temp_root and path.name.startswith("pdf_export_"):
        shutil.rmtree(path, ignore_errors=True)


def get_page_title(page: fitz.Page) -> str:
    data = page.get_text("dict")
    best_span = None

    for block in data.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                y0 = span["bbox"][1]
                size = span["size"]
                if best_span is None:
                    best_span = (text, size, y0)
                else:
                    _, best_size, best_y = best_span
                    if size > best_size + 0.5 or (abs(size - best_size) < 0.5 and y0 < best_y):
                        best_span = (text, size, y0)
    return best_span[0] if best_span else ""


LEGAL_ENTITY_SUFFIX = (
    r"(?:Private\s+(?:Limited|Ltd\.?)|Pvt\.?\s+Ltd\.?|"
    r"Limited|Ltd\.?|LLP|L\.L\.P\.?)"
)

OUTPUT_WIDTHS = {
    1.0: 900,
    1.5: 1200,
    2.0: 1500,
}


def extract_legal_entity_name(text: str) -> str:
    """Extract a company name ending in a common Indian legal suffix."""
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"^[^A-Za-z0-9]+", "", normalized)
    normalized = re.sub(
        r"^(?:portfolio\s+manager|manager|managed\s+by)\s*[:\-]\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    match = re.match(
        rf"^([A-Z][A-Za-z0-9&'().,\-]*(?:\s+[A-Za-z0-9&'().,\-]+){{0,10}}?"
        rf"\s+{LEGAL_ENTITY_SUFFIX})(?=\s|,|$)",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        return ""
    manager_name = match.group(1).strip().rstrip(".,")
    manager_name = re.sub(
        r"\s+(?:Private\s+(?:Limited|Ltd\.?)|Pvt\.?\s+Ltd\.?)$",
        "",
        manager_name,
        flags=re.IGNORECASE,
    )
    return manager_name.strip().rstrip(".,")


def get_lower_right_legal_manager(page: fitz.Page) -> str:
    """Find the legal manager name beneath the SEBI area in the new layout."""
    width = page.rect.width
    height = page.rect.height
    candidate_blocks = []

    for block in page.get_text("blocks", sort=True):
        x0, y0, _x1, _y1, text = block[:5]
        if x0 < width * 0.22 or y0 < height * 0.55 or y0 > height * 0.96:
            continue
        candidate_blocks.append((y0, text))

    for _y0, text in sorted(candidate_blocks):
        # The company description normally starts with the legal entity name.
        for line in text.splitlines():
            manager = extract_legal_entity_name(line)
            if manager:
                return manager
        manager = extract_legal_entity_name(text)
        if manager:
            return manager

    return ""


def get_upper_left_title(page: fitz.Page) -> str:
    """Read the prominent multi-line smallcase title in the new left panel."""
    width = page.rect.width
    height = page.rect.height
    candidate_lines = []

    for block in page.get_text("dict").get("blocks", []):
        lines = block.get("lines", [])
        if not lines:
            continue
        for line in lines:
            spans = line.get("spans", [])
            line_text = " ".join(
                span.get("text", "").strip()
                for span in spans
                if span.get("text", "").strip()
            )
            if not line_text:
                continue
            line_bbox = line.get("bbox")
            if line_bbox is None and spans:
                span_boxes = [
                    span.get("bbox") for span in spans if span.get("bbox")
                ]
                if span_boxes:
                    line_bbox = (
                        min(box[0] for box in span_boxes),
                        min(box[1] for box in span_boxes),
                        max(box[2] for box in span_boxes),
                        max(box[3] for box in span_boxes),
                    )
            if line_bbox is None:
                continue

            x0, y0, x1, y1 = line_bbox
            if x0 > width * 0.38 or x1 > width * 0.52:
                continue
            if y0 < height * 0.12 or y0 > height * 0.42:
                continue
            line_size = max(
                (span.get("size", 0.0) for span in spans),
                default=0.0,
            )
            if line_size >= 12.0:
                candidate_lines.append((y0, y1, line_size, line_text))

    if not candidate_lines:
        return ""

    clusters = []
    for candidate in sorted(candidate_lines):
        y0, _y1, size, _text = candidate
        if not clusters:
            clusters.append([candidate])
            continue
        previous = clusters[-1][-1]
        max_gap = max(14.0, max(previous[2], size) * 1.25)
        if y0 - previous[1] <= max_gap:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])

    best_cluster = max(
        clusters,
        key=lambda cluster: (
            len(cluster),
            sum(item[2] for item in cluster) / len(cluster),
            sum(len(item[3]) for item in cluster),
            -cluster[0][0],
        ),
    )
    return " ".join(item[3] for item in best_cluster).strip()


def pixmap_to_pil_image(pix):
    """Convert a small OCR pixmap to a Pillow image."""
    from PIL import Image

    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def render_ocr_crop(page: fitz.Page, clip: fitz.Rect, target_width: int = 950):
    """Render only a small page region at an OCR-friendly resolution."""
    scale = max(0.5, min(3.0, target_width / max(clip.width, 1)))
    pix = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        clip=clip,
        alpha=False,
    )
    try:
        return pixmap_to_pil_image(pix)
    finally:
        del pix


def get_ocr_region(
    page: fitz.Page,
    relative_box: tuple[float, float, float, float],
    target_width: int,
):
    """Render only the text band needed for OCR and enhance its contrast."""
    from PIL import ImageOps

    width = page.rect.width
    height = page.rect.height
    left, top, right, bottom = relative_box
    crop = render_ocr_crop(
        page,
        fitz.Rect(
            width * left,
            height * top,
            width * right,
            height * bottom,
        ),
        target_width=target_width,
    )

    enhanced = ImageOps.autocontrast(ImageOps.grayscale(crop), cutoff=1)
    crop.close()
    bordered = ImageOps.expand(enhanced, border=24, fill="white")
    enhanced.close()
    return bordered


def ensure_ocr_available():
    """Fail clearly when Streamlit did not install the OCR dependencies."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise RuntimeError(
            "This PDF contains image-only pages, but OCR is unavailable. "
            "Commit both requirements.txt and packages.txt to the repository "
            "root, then reboot the Streamlit app."
        ) from exc


def get_ocr_title(page: fitz.Page) -> str:
    """OCR the upper-left title and select its largest contiguous line group."""
    import pytesseract
    from pytesseract import Output

    image = get_ocr_region(
        page,
        (0.02, 0.12, 0.36, 0.35),
        target_width=900,
    )
    try:
        data = pytesseract.image_to_data(
            image,
            config="--oem 1 --psm 6",
            output_type=Output.DICT,
            timeout=15,
        )
    finally:
        image.close()

    grouped_lines = {}
    for index, word in enumerate(data.get("text", [])):
        word = word.strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1
        if not word or confidence < 20:
            continue
        key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped_lines.setdefault(key, []).append({
            "text": word,
            "top": data["top"][index],
            "height": data["height"][index],
        })

    lines = []
    for words in grouped_lines.values():
        lines.append({
            "text": " ".join(word["text"] for word in words),
            "top": min(word["top"] for word in words),
            "height": max(word["height"] for word in words),
        })
    if not lines:
        return ""

    largest_height = max(line["height"] for line in lines)
    prominent = [
        line for line in lines if line["height"] >= largest_height * 0.68
    ]
    clusters = []
    for line in sorted(prominent, key=lambda item: item["top"]):
        if not clusters:
            clusters.append([line])
            continue
        previous = clusters[-1][-1]
        previous_bottom = previous["top"] + previous["height"]
        if line["top"] - previous_bottom <= largest_height * 1.35:
            clusters[-1].append(line)
        else:
            clusters.append([line])

    best_cluster = max(
        clusters,
        key=lambda cluster: (
            len(cluster),
            sum(line["height"] for line in cluster) / len(cluster),
            sum(len(line["text"]) for line in cluster),
            -cluster[0]["top"],
        ),
    )
    return " ".join(line["text"] for line in best_cluster).strip()


def extract_manager_from_ocr_text(text: str) -> str:
    """Extract a legal entity or company name from the manager description."""
    def company_before_description(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"^[^A-Za-z0-9]+", "", value)
        match = re.match(
            r"^([A-Z][A-Za-z0-9&'().,\-]*(?:\s+[A-Za-z0-9&'().,\-]+){0,7}?)"
            r"\s+(?:builds?|provides?|offers?|manages?|creates?|is|speciali[sz]es?)\b",
            value,
            re.IGNORECASE,
        )
        return match.group(1).strip().rstrip(".,") if match else ""

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        manager = extract_legal_entity_name(line)
        if manager:
            return manager
        manager = company_before_description(line)
        if manager:
            return manager

    # OCR may put the company and the opening verb on adjacent lines.
    return company_before_description(text)


def get_ocr_manager(page: fitz.Page) -> str:
    """OCR the manager/company description beneath the lower-right SEBI area."""
    import pytesseract

    image = get_ocr_region(
        page,
        (0.40, 0.80, 0.97, 0.93),
        target_width=1300,
    )
    try:
        text = pytesseract.image_to_string(
            image,
            config="--oem 1 --psm 6",
            timeout=15,
        )
    finally:
        image.close()
    return extract_manager_from_ocr_text(text)


def get_ocr_page_identity(page: fitz.Page) -> tuple[str, str]:
    """Return OCR title and manager, degrading safely if OCR is unavailable."""
    try:
        title = get_ocr_title(page)
    except Exception:
        title = ""
    try:
        manager = get_ocr_manager(page)
    except Exception:
        manager = ""
    return title, manager


def get_manager_name(page: fitz.Page) -> str:
    """Return the value next to or below a supported manager label."""
    lines = [
        re.sub(r'\s+', ' ', line).strip()
        for line in page.get_text("text", sort=True).splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines):
        match = re.match(
            r'^(?:research\s+analyst|investment\s+advisor)\b\s*[:\-]?\s*(.*)$',
            line,
            re.IGNORECASE,
        )
        if not match:
            continue

        # Some PDFs place the value on the same line as the label.
        inline_value = match.group(1).strip()
        if inline_value:
            return inline_value

        # In the usual report layout, the value is the next extracted line.
        if index + 1 < len(lines):
            return lines[index + 1]

    return ""


def convert_pdf_bytes(
    pdf_bytes: bytes,
    original_name: str,
    output_dir: Path,
    zoom: float = 2.0,
    progress_callback=None,
):
    """Render every page to temporary disk to keep Streamlit memory bounded."""
    results = []
    used_filenames = {}
    pdf_stem = safe_name(Path(original_name).stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_dir = output_dir / "thumbnails"
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    source_pdf_path = output_dir / safe_pdf_name(original_name)
    pdf_bytes.seek(0)
    with source_pdf_path.open("wb") as source_pdf:
        shutil.copyfileobj(pdf_bytes, source_pdf, length=1024 * 1024)
    doc = fitz.open(str(source_pdf_path))
    try:
        total_pages = len(doc)
        ocr_checked = False
        for i, page in enumerate(doc, start=1):
            page_text = page.get_text("text", sort=True).strip()
            if len(page_text) < 20:
                if not ocr_checked:
                    ensure_ocr_available()
                    ocr_checked = True
                title_raw, manager_raw = get_ocr_page_identity(page)
            else:
                legal_manager = get_lower_right_legal_manager(page)
                manager_raw = legal_manager or get_manager_name(page)
                title_raw = (
                    get_upper_left_title(page)
                    if legal_manager
                    else get_page_title(page)
                )
            title_raw = title_raw or get_page_title(page) or f"Page {i:03d}"
            display_name = (
                f"{title_raw} by {manager_raw}" if manager_raw else title_raw
            )
            title = safe_name(display_name)
            base_filename = f"{title}.png"
            filename_key = base_filename.casefold()
            used_filenames[filename_key] = used_filenames.get(filename_key, 0) + 1
            occurrence = used_filenames[filename_key]
            filename = (
                base_filename
                if occurrence == 1
                else f"{title} ({occurrence}).png"
            )

            target_width = OUTPUT_WIDTHS.get(zoom, 900)
            render_scale = target_width / max(page.rect.width, 1)
            pix = page.get_pixmap(
                matrix=fitz.Matrix(render_scale, render_scale),
                alpha=False,
            )
            image_path = output_dir / filename
            pix.save(str(image_path))
            del pix
            thumbnail_scale = 280 / max(page.rect.width, 1)
            thumbnail_pix = page.get_pixmap(
                matrix=fitz.Matrix(thumbnail_scale, thumbnail_scale),
                alpha=False,
            )
            thumbnail_path = thumbnail_dir / filename
            thumbnail_pix.save(str(thumbnail_path))
            del thumbnail_pix
            results.append({
                "page": i,
                "title": title,
                "folder": pdf_stem,
                "filename": filename,
                "image_path": str(image_path),
                "thumbnail_path": str(thumbnail_path),
            })
            if progress_callback is not None:
                progress_callback(i, total_pages)
            # Periodically reclaim cyclic buffers without slowing every page.
            if i % 4 == 0:
                gc.collect()
    finally:
        doc.close()

    return total_pages, results, str(source_pdf_path)


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def output_zip_name(original_name: str) -> str:
    return f"{safe_name(Path(original_name).stem)}_images.zip"


def build_output_zip(output: dict, results: list[dict]) -> str:
    """Build or reuse a ZIP containing the source PDF and selected pages."""
    signature = "pdf+|" + "|".join(
        f"{item['page']}:{item['filename']}" for item in results
    )
    zip_path = Path(output["working_dir"]) / "selected_images.zip"
    if output.get("zip_signature") == signature and zip_path.exists():
        return str(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as archive:
        package_folder = safe_name(Path(output["original_name"]).stem)
        archive.write(
            output["source_pdf_path"],
            f"{package_folder}/{safe_pdf_name(output['original_name'])}",
        )
        for item in results:
            archive.write(
                item["image_path"],
                f"{package_folder}/{item['filename']}",
            )
    output["zip_signature"] = signature
    return str(zip_path)


def page_selection_key(output: dict, output_index: int, page: int) -> str:
    batch_id = output.get("batch_id", "current")
    return f"keep_page_{batch_id}_{output_index}_{page}"


def page_rename_key(output: dict, output_index: int, page: int) -> str:
    batch_id = output.get("batch_id", "current")
    return f"rename_page_{batch_id}_{output_index}_{page}"


def apply_page_rename(
    output: dict,
    item: dict,
    rename_key: str,
):
    """Apply a safe, unique PNG filename entered in the review screen."""
    requested = str(st.session_state.get(rename_key, "")).strip()
    requested = re.sub(r"\.png$", "", requested, flags=re.IGNORECASE)
    requested = safe_name(requested)
    candidate = f"{requested}.png"
    existing_names = {
        other["filename"].casefold()
        for other in output["results"]
        if other["page"] != item["page"]
    }
    if candidate.casefold() in existing_names:
        candidate = f"{requested} (page {item['page']}).png"
        st.session_state[rename_key] = Path(candidate).stem
    item["filename"] = candidate
    item["title"] = Path(candidate).stem
    output["zip_signature"] = None


def selected_output(output: dict, output_index: int) -> dict:
    """Return selected pages without eagerly building a download in memory."""
    if output["error"] is not None:
        return output

    kept_results = [
        item
        for item in output["results"]
        if st.session_state.get(
            page_selection_key(output, output_index, item["page"]),
            True,
        )
    ]
    filtered = dict(output)
    filtered["results"] = kept_results
    filtered["zip_path"] = None
    return filtered


def render_page_review(output: dict, output_index: int):
    """Render bin actions for kept pages and restore actions for removed pages."""
    kept_items = []
    removed_items = []
    for item in output["results"]:
        selection_key = page_selection_key(output, output_index, item["page"])
        if selection_key not in st.session_state:
            st.session_state[selection_key] = True
        if st.session_state[selection_key]:
            kept_items.append(item)
        else:
            removed_items.append(item)

    with st.expander(
        f"Review images — {len(kept_items)} of {len(output['results'])} kept",
        expanded=False,
    ):
        st.caption(
            "Use the bin button to remove an image. Downloads and Drive sync "
            "automatically include only the images that remain."
        )
        keep_col, remove_col = st.columns(2)
        if keep_col.button(
            "Restore all",
            icon=":material/restore:",
            key=f"keep_all_{output.get('batch_id', 'current')}_{output_index}",
            disabled=not removed_items,
            use_container_width=True,
        ):
            for item in output["results"]:
                st.session_state[
                    page_selection_key(output, output_index, item["page"])
                ] = True
            st.rerun()
        if remove_col.button(
            "Delete all",
            icon=":material/delete_sweep:",
            key=f"remove_all_{output.get('batch_id', 'current')}_{output_index}",
            disabled=not kept_items,
            use_container_width=True,
        ):
            for item in output["results"]:
                st.session_state[
                    page_selection_key(output, output_index, item["page"])
                ] = False
            st.rerun()

        if not kept_items:
            st.info(
                "No images are currently selected. Restore an image to "
                "enable download and Drive sync."
            )

        page_size = 6
        page_group_count = max(
            1,
            (len(output["results"]) + page_size - 1) // page_size,
        )
        if page_group_count > 1:
            page_group = st.selectbox(
                "Images to review",
                options=list(range(page_group_count)),
                format_func=lambda group: (
                    f"Pages {group * page_size + 1}–"
                    f"{min((group + 1) * page_size, len(output['results']))}"
                ),
                key=(
                    f"review_group_{output.get('batch_id', 'current')}_"
                    f"{output_index}"
                ),
            )
        else:
            page_group = 0

        visible_items = output["results"][
            page_group * page_size:(page_group + 1) * page_size
        ]

        # Render every visible page in its original grid position. Keeping stable
        # element positions prevents Streamlit from reusing a deleted page's
        # thumbnail for the next page during reruns.
        review_columns = st.columns(3)
        for item_index, item in enumerate(visible_items):
            with review_columns[item_index % len(review_columns)]:
                selection_key = page_selection_key(
                    output,
                    output_index,
                    item["page"],
                )
                image_slot = st.empty()
                if st.session_state[selection_key]:
                    image_slot.image(
                        item["thumbnail_path"],
                        caption=f"Page {item['page']} · {item['filename']}",
                        use_container_width=True,
                    )
                    rename_key = page_rename_key(
                        output,
                        output_index,
                        item["page"],
                    )
                    if rename_key not in st.session_state:
                        st.session_state[rename_key] = Path(
                            item["filename"]
                        ).stem
                    st.text_input(
                        f"Filename for page {item['page']}",
                        key=rename_key,
                        on_change=apply_page_rename,
                        args=(output, item, rename_key),
                        help="Edit the detected name if OCR needs correction. "
                        "The .png extension is added automatically.",
                    )
                    if st.button(
                        f"Delete page {item['page']}",
                        icon=":material/delete:",
                        key=f"delete_{selection_key}",
                        use_container_width=True,
                    ):
                        st.session_state[selection_key] = False
                        st.rerun()
                else:
                    image_slot.markdown(
                        '<div class="removed-image-slot">'
                        '<div><strong>Image removed</strong>'
                        f'<span>Page {item["page"]} is excluded from output</span></div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"Restore page {item['page']}",
                        icon=":material/undo:",
                        key=f"restore_{selection_key}",
                        use_container_width=True,
                    ):
                        st.session_state[selection_key] = True
                        st.rerun()


def create_batch_zip(outputs: list[dict]) -> str:
    """Bundle disk-backed per-PDF ZIPs without loading them into memory."""
    batch_dir = Path(outputs[0]["working_dir"]).parent
    batch_path = batch_dir / "all_pdf_image_zips.zip"
    signature = "|".join(
        f"{output['original_name']}:{output.get('zip_signature', '')}"
        for output in outputs
    )
    cache_key = f"batch_zip_signature_{outputs[0].get('batch_id', 'current')}"
    if st.session_state.get(cache_key) == signature and batch_path.exists():
        return str(batch_path)

    used_names = {}

    # The inner files are already compressed ZIPs, so storing them directly
    # avoids wasting time trying to compress the same bytes again.
    with zipfile.ZipFile(batch_path, "w", zipfile.ZIP_STORED) as archive:
        for output in outputs:
            if output["error"] is not None or not output["results"]:
                continue

            base_name = output_zip_name(output["original_name"])
            used_names[base_name] = used_names.get(base_name, 0) + 1
            occurrence = used_names[base_name]
            if occurrence == 1:
                archive_name = base_name
            else:
                zip_path = Path(base_name)
                archive_name = f"{zip_path.stem} ({occurrence}){zip_path.suffix}"

            archive.write(output["zip_path"], archive_name)

    st.session_state[cache_key] = signature
    return str(batch_path)


def get_google_drive_config():
    """Read optional OAuth settings without breaking the core converter."""
    try:
        config = st.secrets["google_drive"]
        required = ("client_id", "client_secret", "redirect_uri")
        if not all(config.get(key) for key in required):
            return None
        return config
    except (FileNotFoundError, KeyError):
        return None


def build_drive_service(token: dict, config):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    expiry = None
    if token.get("expires_at"):
        # google-auth compares expiry with a naive UTC datetime internally.
        expiry = datetime.utcfromtimestamp(float(token["expires_at"]))
    elif token.get("expires_in") and token.get("obtained_at"):
        expiry = datetime.utcfromtimestamp(
            float(token["obtained_at"]) + float(token["expires_in"])
        )

    credentials = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scopes=[GOOGLE_DRIVE_SCOPE],
        expiry=expiry,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def collect_report_files(outputs: list[dict]) -> list[tuple[str, str, str]]:
    """Return each source PDF and its selected PNGs without copying data."""
    files = []
    used_names = {}

    for output in outputs:
        if output["error"] is not None or not output["results"]:
            continue
        source_name = safe_pdf_name(output["original_name"])
        source_key = source_name.casefold()
        used_names[source_key] = used_names.get(source_key, 0) + 1
        source_occurrence = used_names[source_key]
        if source_occurrence > 1:
            source_path = Path(source_name)
            source_name = (
                f"{source_path.stem} ({source_occurrence}){source_path.suffix}"
            )
        files.append(
            (source_name, output["source_pdf_path"], "application/pdf")
        )
        for item in output["results"]:
            base_name = Path(item["filename"]).name
            name_key = base_name.casefold()
            used_names[name_key] = used_names.get(name_key, 0) + 1
            occurrence = used_names[name_key]
            if occurrence == 1:
                image_name = base_name
            else:
                image_path = Path(base_name)
                image_name = (
                    f"{image_path.stem} ({occurrence}){image_path.suffix}"
                )
            files.append((image_name, item["image_path"], "image/png"))

    return files


def list_folder_contents(service, folder_id: str) -> list[dict]:
    contents = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields=(
                "nextPageToken, files(id, name, mimeType, "
                "capabilities(canTrash))"
            ),
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        contents.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return contents


def list_child_folders(service, root_folder_id: str) -> tuple[dict, list[dict]]:
    """Return a Drive folder and its immediate, non-trashed child folders."""
    root_folder = service.files().get(
        fileId=root_folder_id,
        fields="id, name, mimeType",
        supportsAllDrives=True,
    ).execute()
    if root_folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise ValueError("The configured Google Drive root is not a folder.")

    folders = []
    page_token = None
    while True:
        response = service.files().list(
            q=(
                f"'{root_folder_id}' in parents and trashed = false and "
                "mimeType = 'application/vnd.google-apps.folder'"
            ),
            fields=(
                "nextPageToken, files(id, name, "
                "capabilities(canAddChildren))"
            ),
            orderBy="name_natural",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        folders.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return root_folder, folders


def is_replaceable_drive_asset(item: dict) -> bool:
    """Identify direct PDF/PNG/JPG files, excluding folders and other files."""
    mime_type = (item.get("mimeType") or "").casefold()
    if mime_type == "application/vnd.google-apps.folder":
        return False
    return mime_type in {"application/pdf", "image/png", "image/jpeg"} or Path(
        item.get("name", "")
    ).suffix.casefold() in {".pdf", ".png", ".jpg", ".jpeg"}


def replace_drive_folder(
    service,
    folder_id: str,
    report_files: list[tuple[str, str, str]],
):
    """Replace direct PDF/image files, with best-effort rollback on error."""
    from googleapiclient.http import MediaFileUpload

    folder = service.files().get(
        fileId=folder_id,
        fields="id, name, capabilities(canAddChildren)",
        supportsAllDrives=True,
    ).execute()
    if not folder.get("capabilities", {}).get("canAddChildren", False):
        raise PermissionError("You do not have permission to add files to this folder.")

    existing_items = [
        item
        for item in list_folder_contents(service, folder_id)
        if is_replaceable_drive_asset(item)
    ]
    blocked_items = [
        item["name"]
        for item in existing_items
        if not item.get("capabilities", {}).get("canTrash", False)
    ]
    if blocked_items:
        sample = ", ".join(blocked_items[:3])
        raise PermissionError(
            "The folder contains items you cannot move to Trash: " + sample
        )

    uploaded_ids = []
    trashed_ids = []
    try:
        # Upload first. If an upload fails, the old folder remains unchanged.
        for file_name, file_path, mime_type in report_files:
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=False,
            )
            created = service.files().create(
                body={"name": file_name, "parents": [folder_id]},
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            uploaded_ids.append(created["id"])

        # All uploads succeeded; move previous direct report files to Trash.
        for item in existing_items:
            service.files().update(
                fileId=item["id"],
                body={"trashed": True},
                fields="id",
                supportsAllDrives=True,
            ).execute()
            trashed_ids.append(item["id"])
    except Exception:
        # Restore any old items already moved, and remove partial new uploads.
        for file_id in trashed_ids:
            try:
                service.files().update(
                    fileId=file_id,
                    body={"trashed": False},
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception:
                pass
        for file_id in uploaded_ids:
            try:
                service.files().update(
                    fileId=file_id,
                    body={"trashed": True},
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception:
                pass
        raise

    return folder["name"], len(existing_items), len(uploaded_ids)


def parse_drive_folder_id(value: str) -> str | None:
    """Accept a Google Drive folder URL or a raw Drive folder ID."""
    value = value.strip()
    if not value:
        return None
    url_match = re.search(r"/folders/([A-Za-z0-9_-]+)", value)
    if url_match:
        return url_match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value
    return None


def render_drive_connection(outputs: list[dict]):
    with st.container(border=True):
        st.header("Google Drive sync")
        st.caption(
            "Connect once, then choose a broker subfolder beside each report."
        )

        report_files = collect_report_files(outputs)
        if not report_files:
            st.info("Convert at least one eligible PDF page to enable Drive sync.")
            return None, []

        config = get_google_drive_config()
        if config is None:
            st.warning(
                "Drive sync is not configured yet. Add the `[google_drive]` "
                "credentials in your Streamlit app secrets."
            )
            return None, []

        try:
            from streamlit_oauth import OAuth2Component
        except ImportError:
            st.error("Drive sync dependencies are not installed yet.")
            return None, []

        oauth = OAuth2Component(
            config["client_id"],
            config["client_secret"],
            GOOGLE_AUTHORIZE_URL,
            GOOGLE_TOKEN_URL,
            GOOGLE_TOKEN_URL,
            GOOGLE_REVOKE_URL,
        )

        if "google_drive_token" not in st.session_state:
            result = oauth.authorize_button(
                "Connect Google Drive",
                config["redirect_uri"],
                GOOGLE_DRIVE_SCOPE,
                key="google_drive_oauth",
                use_container_width=True,
                extras_params={
                    "access_type": "offline",
                    "prompt": "consent",
                    "include_granted_scopes": "true",
                },
            )
            if result and result.get("token"):
                token = dict(result["token"])
                token["obtained_at"] = time.time()
                st.session_state.google_drive_token = token
                st.rerun()
            return None, []

        status_col, disconnect_col = st.columns([1.7, 1], vertical_alignment="center")
        with status_col:
            st.success("Google Drive is connected.")
        with disconnect_col:
            if st.button("Disconnect Drive", use_container_width=True):
                try:
                    oauth.revoke_token(st.session_state.google_drive_token)
                except Exception:
                    pass
                st.session_state.pop("google_drive_token", None)
                st.rerun()

        try:
            # google-auth refreshes expired access tokens during API requests.
            service = build_drive_service(
                st.session_state.google_drive_token,
                config,
            )
            root_folder, broker_folders = list_child_folders(
                service,
                DRIVE_ROOT_FOLDER_ID,
            )
        except Exception as exc:
            st.error(f"Google Drive connection failed: {exc}")
            if st.button("Reconnect Drive", use_container_width=True):
                st.session_state.pop("google_drive_token", None)
                st.rerun()
            return None, []

        root_col, refresh_col = st.columns([1.7, 1], vertical_alignment="center")
        with root_col:
            st.markdown(
                f"**Root folder:** [{root_folder['name']}]({DRIVE_ROOT_FOLDER_URL})  "
                f"\n{len(broker_folders)} immediate broker subfolder"
                f"{'s' if len(broker_folders) != 1 else ''} found."
            )
        with refresh_col:
            if st.button("Refresh broker folders", use_container_width=True):
                st.rerun()

        if not broker_folders:
            st.warning(
                "No immediate subfolders are visible inside the configured root folder."
            )

        return service, broker_folders


def render_report_drive_sync(
    service,
    broker_folders: list[dict],
    output: dict,
    output_index: int,
):
    report_files = collect_report_files([output])
    if not report_files:
        return
    png_count = len(output["results"])

    if service is None or not broker_folders:
        st.button(
            "Sync to Drive",
            key=f"drive_disabled_{output_index}",
            disabled=True,
            help="Connect Google Drive and load its broker subfolders above.",
            use_container_width=True,
        )
        return

    with st.popover("Sync to Drive", use_container_width=True):
        st.write(f"Choose where to sync **{output['original_name']}**.")

        name_counts = {}
        for folder in broker_folders:
            name_key = folder["name"].casefold()
            name_counts[name_key] = name_counts.get(name_key, 0) + 1

        def folder_label(folder: dict) -> str:
            if name_counts[folder["name"].casefold()] == 1:
                return folder["name"]
            return f"{folder['name']} · {folder['id'][-6:]}"

        selected_folder = st.selectbox(
            "Broker folder",
            options=broker_folders,
            format_func=folder_label,
            key=f"drive_broker_folder_{output_index}",
            help="Only immediate subfolders of the configured Drive root are shown.",
        )
        folder_id = selected_folder["id"]
        selected_folder_name = selected_folder["name"]

        st.warning(
            f"This will move all PDF, PNG, and JPG files directly inside "
            f"“{selected_folder_name}” to Drive Trash, then upload the original "
            f"PDF and {png_count} selected PNG{'s' if png_count != 1 else ''}. "
            "Other file types and nested folders will remain untouched."
        )
        confirmed = st.checkbox(
            f"Replace the existing report files in “{selected_folder_name}”.",
            key=f"drive_sync_confirm_{output_index}",
        )
        sync_clicked = st.button(
            f"Sync PDF + {png_count} PNG{'s' if png_count != 1 else ''}",
            type="primary",
            disabled=not confirmed,
            key=f"drive_sync_{output_index}",
            use_container_width=True,
        )

        if sync_clicked:
            with st.spinner("Replacing this Drive folder..."):
                try:
                    folder_name, removed_count, uploaded_count = replace_drive_folder(
                        service,
                        folder_id,
                        report_files,
                    )
                except Exception as exc:
                    st.error(f"Drive sync failed: {exc}")
                else:
                    st.success(
                        f"Synced {uploaded_count} files: the PDF and {png_count} PNG"
                        f"{'s' if png_count != 1 else ''} to “{folder_name}”. "
                        f"Moved {removed_count} previous report files to Trash."
                    )


st.markdown(
    """
    <div class="app-hero">
        <div class="app-mark">PNG</div>
        <div class="app-hero-copy">
            <h1>PDF page exporter</h1>
            <p>Turn PDF reports into neatly named PNGs, review every page, and send the finished package exactly where it needs to go.</p>
            <div class="hero-meta" aria-label="Output details">
                <span>Original PDF included</span>
                <span>Editable filenames</span>
                <span>ZIP or Google Drive</span>
            </div>
        </div>
    </div>
    <div class="workflow-note" aria-label="Conversion steps">
        <span><strong>1.</strong> Select one or more PDFs</span>
        <span><strong>2.</strong> Review, rename, or delete images</span>
        <span><strong>3.</strong> Download or sync the pages you keep</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Upload PDFs")
st.caption("Add one or more reports. Each PDF is processed as its own package.")
st.markdown(
    '<div class="conversion-note"><strong>Every page is converted.</strong> '
    'Portfolio pages are named <code>Smallcase by Manager</code>; other pages '
    'use their detected title. You can correct any filename or remove unwanted '
    'pages before export. The original PDF is always included with the PNGs '
    'you keep.</div>',
    unsafe_allow_html=True,
)
uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Drag and drop several PDF files here, or browse to select them.",
    label_visibility="collapsed",
)

control_col, action_col = st.columns([1.15, 1], vertical_alignment="bottom")
with control_col:
    zoom = st.select_slider(
        "Image resolution",
        options=[1.0, 1.5, 2.0],
        value=1.0,
        format_func=lambda value: {
            1.0: "Standard",
            1.5: "Balanced",
            2.0: "High",
        }[value],
        help=(
            "Standard is recommended on Streamlit Community Cloud. Higher "
            "resolutions create sharper PNGs but use more memory."
        ),
    )

file_count = len(uploaded_files) if uploaded_files else 0
with action_col:
    process = st.button(
        f"Convert {file_count} PDF{'s' if file_count != 1 else ''}",
        type="primary",
        disabled=not uploaded_files,
        use_container_width=True,
    )

if uploaded_files:
    total_upload_size = sum(uploaded.size for uploaded in uploaded_files)
    st.info(
        f"Ready to process {file_count} PDF{'s' if file_count != 1 else ''} "
        f"({format_file_size(total_upload_size)} total)."
    )

if st.session_state.get("app_state_version") != APP_STATE_VERSION:
    cleanup_batch_temp_dir(st.session_state.get("batch_temp_dir"))
    st.session_state.pop("batch_temp_dir", None)
    st.session_state.conversion_outputs = []
    st.session_state.app_state_version = APP_STATE_VERSION
elif "conversion_outputs" not in st.session_state:
    st.session_state.conversion_outputs = []
elif any(
    output.get("results")
    and "image_path" not in output["results"][0]
    for output in st.session_state.conversion_outputs
):
    # Results created by an older in-memory app version cannot be reused.
    cleanup_batch_temp_dir(st.session_state.get("batch_temp_dir"))
    st.session_state.pop("batch_temp_dir", None)
    st.session_state.conversion_outputs = []

if process and uploaded_files:
    cleanup_batch_temp_dir(st.session_state.get("batch_temp_dir"))
    batch_temp_dir = tempfile.mkdtemp(prefix="pdf_export_")
    st.session_state.batch_temp_dir = batch_temp_dir
    batch_root = Path(batch_temp_dir)
    batch_outputs = []
    batch_id = time.time_ns()
    progress_bar = st.progress(0)
    progress_text = st.empty()

    for index, uploaded in enumerate(uploaded_files, start=1):
        progress_text.caption(f"Opening {index} of {file_count}: {uploaded.name}")
        working_dir = batch_root / f"{index}_{safe_name(Path(uploaded.name).stem)}"

        def update_page_progress(page_number, total_pages):
            overall_progress = (
                (index - 1) + (page_number / max(total_pages, 1))
            ) / file_count
            progress_bar.progress(min(overall_progress, 1.0))
            progress_text.caption(
                f"Processing {index} of {file_count}: {uploaded.name} — "
                f"page {page_number} of {total_pages}"
            )

        try:
            uploaded.seek(0)
            total_pages, results, source_pdf_path = convert_pdf_bytes(
                uploaded,
                uploaded.name,
                working_dir,
                zoom=zoom,
                progress_callback=update_page_progress,
            )
            batch_outputs.append({
                "batch_id": batch_id,
                "original_name": uploaded.name,
                "total_pages": total_pages,
                "results": results,
                "working_dir": str(working_dir),
                "source_pdf_path": source_pdf_path,
                "zip_signature": None,
                "error": None,
            })
        except Exception as exc:
            batch_outputs.append({
                "batch_id": batch_id,
                "original_name": uploaded.name,
                "total_pages": 0,
                "results": [],
                "working_dir": str(working_dir),
                "source_pdf_path": None,
                "zip_signature": None,
                "error": str(exc),
            })
        progress_bar.progress(index / file_count)

    st.session_state.conversion_outputs = batch_outputs
    progress_bar.empty()
    progress_text.empty()

if st.session_state.conversion_outputs:
    st.divider()
    st.subheader("Your downloads")
    st.caption(
        "Each report ZIP contains its original PDF and the PNG pages you kept. "
        "You can also download one master ZIP containing every report package."
    )

    selected_conversion_outputs = [
        selected_output(output, output_index)
        for output_index, output in enumerate(st.session_state.conversion_outputs)
    ]

    drive_service, broker_folders = render_drive_connection(
        selected_conversion_outputs
    )

    successful_outputs = sum(
        output["error"] is None for output in st.session_state.conversion_outputs
    )
    downloadable_outputs = [
        output
        for output in selected_conversion_outputs
        if output["error"] is None and output["results"]
    ]

    if successful_outputs:
        st.success(
            f"Finished {successful_outputs} of "
            f"{len(st.session_state.conversion_outputs)} PDF files."
        )

    # Streamlit keeps download payloads in memory. Offer one selected payload
    # at a time instead of preloading every report ZIP plus the master ZIP.
    if downloadable_outputs:
        download_options = [
            f"report:{index}" for index, output in enumerate(
                selected_conversion_outputs
            )
            if output["error"] is None and output["results"]
        ]
        if len(downloadable_outputs) > 1:
            download_options.append("all")

        def download_label(option: str) -> str:
            if option == "all":
                return f"All {len(downloadable_outputs)} report ZIPs"
            output_index = int(option.split(":", 1)[1])
            return selected_conversion_outputs[output_index]["original_name"]

        selector_col, button_col = st.columns(
            [1.7, 1],
            vertical_alignment="bottom",
        )
        with selector_col:
            download_choice = st.selectbox(
                "Choose a download",
                options=download_options,
                format_func=download_label,
                key="download_choice",
            )

        if download_choice == "all":
            prepared_outputs = []
            for output_index, output in enumerate(selected_conversion_outputs):
                if output["error"] is not None or not output["results"]:
                    continue
                source_output = st.session_state.conversion_outputs[output_index]
                prepared = dict(output)
                prepared["zip_path"] = build_output_zip(
                    source_output,
                    output["results"],
                )
                prepared["zip_signature"] = source_output["zip_signature"]
                prepared_outputs.append(prepared)
            download_path = create_batch_zip(prepared_outputs)
            download_name = "all_pdf_image_zips.zip"
            download_text = f"Download all {len(prepared_outputs)} ZIPs"
        else:
            chosen_index = int(download_choice.split(":", 1)[1])
            chosen_output = selected_conversion_outputs[chosen_index]
            source_output = st.session_state.conversion_outputs[chosen_index]
            download_path = build_output_zip(
                source_output,
                chosen_output["results"],
            )
            download_name = output_zip_name(chosen_output["original_name"])
            download_text = "Download selected ZIP"

        with button_col:
            with open(download_path, "rb") as selected_zip_file:
                st.download_button(
                    label=download_text,
                    data=selected_zip_file,
                    file_name=download_name,
                    mime="application/zip",
                    key=f"download_selected_{download_choice}",
                    use_container_width=True,
                )

    for output_index, (source_output, output) in enumerate(
        zip(st.session_state.conversion_outputs, selected_conversion_outputs)
    ):
        with st.container(border=True):
            if output["error"]:
                st.subheader(output["original_name"])
                st.error(f"This PDF could not be processed: {output['error']}")
                continue

            result_col, drive_col = st.columns(
                [2.5, 0.8],
                vertical_alignment="center",
            )
            with result_col:
                st.subheader(output["original_name"])
                converted_count = len(output["results"])
                total_pages = output["total_pages"]
                removed_count = total_pages - converted_count
                st.markdown(
                    '<div class="result-counts">'
                    f'<span><strong>{total_pages}</strong> total pages</span>'
                    f'<span><strong>{converted_count}</strong> kept</span>'
                    f'<span><strong>{removed_count}</strong> removed</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="package-note"><strong>Package:</strong> original '
                    f'PDF + {converted_count} selected PNG'
                    f'{"s" if converted_count != 1 else ""}</div>',
                    unsafe_allow_html=True,
                )
            with drive_col:
                if converted_count:
                    render_report_drive_sync(
                        drive_service,
                        broker_folders,
                        output,
                        output_index,
                    )

            if not converted_count:
                st.warning(
                    "All pages are currently removed. Keep at least one page to "
                    "enable download and Drive sync."
                )

            render_page_review(source_output, output_index)
