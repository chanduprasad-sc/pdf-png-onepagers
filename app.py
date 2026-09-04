from pathlib import Path
from datetime import datetime
import re
import zipfile
import time
import tempfile
import shutil

import fitz  # PyMuPDF
import streamlit as st

GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DRIVE_ROOT_FOLDER_ID = "1R_fjJmLYUqLPsphGIy1saPo9vP9o7Cp4"
DRIVE_ROOT_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    f"{DRIVE_ROOT_FOLDER_ID}"
)

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
            --ink: oklch(0.19 0.025 140);
            --muted: oklch(0.46 0.02 140);
            --line: oklch(0.88 0.012 140);
            --primary: oklch(0.35 0.11 140);
            --primary-hover: oklch(0.30 0.105 140);
            --accent: oklch(0.58 0.13 235);
            --focus: var(--accent);
        }

        html { color-scheme: light; }
        .stApp { background: var(--app-bg); color: var(--ink); }
        .block-container {
            max-width: 1080px;
            padding-top: 3.5rem;
            padding-bottom: 5rem;
        }
        header[data-testid="stHeader"] { background: transparent; }

        .app-hero {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 2.5rem;
        }
        .app-mark {
            display: grid;
            place-items: center;
            width: 3.25rem;
            height: 3.25rem;
            flex: 0 0 auto;
            border-radius: 0.8rem;
            background: var(--primary);
            color: oklch(1 0 0);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.04em;
            box-shadow: 0 0.5rem 1.5rem oklch(0.35 0.11 140 / 0.18);
        }
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
        .workflow-note {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem 1.25rem;
            margin: -1rem 0 2.25rem;
            color: var(--muted);
            font-size: 0.875rem;
        }
        .workflow-note span { white-space: nowrap; }
        .workflow-note strong { color: var(--ink); }

        h2, h3 { color: var(--ink); letter-spacing: -0.015em; }
        div[data-testid="stFileUploaderDropzone"] {
            min-height: 12rem;
            border: 1.5px dashed var(--line) !important;
            border-radius: 0.9rem;
            background: var(--surface) !important;
            color: var(--ink) !important;
            transition: border-color 180ms ease-out, background 180ms ease-out;
        }
        div[data-testid="stFileUploaderDropzone"]:hover {
            border-color: var(--focus) !important;
            background: var(--surface-subtle) !important;
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
            border-radius: 0.65rem;
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
            border-radius: 0.65rem;
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

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line) !important;
            border-radius: 0.9rem !important;
            background: var(--surface);
            box-shadow: 0 0.35rem 1.5rem oklch(0.19 0.025 140 / 0.045);
        }
        div[data-testid="stAlert"] { border-radius: 0.65rem; }
        div[data-testid="stExpander"] {
            border-color: var(--line);
            border-radius: 0.65rem;
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
            gap: 0.5rem 1.15rem;
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
        }
        .result-counts strong { color: var(--ink); font-weight: 700; }

        @media (max-width: 640px) {
            .block-container { padding-top: 2rem; }
            .app-hero { align-items: flex-start; }
            .app-hero h1 { font-size: 1.65rem; }
            .app-mark { width: 2.8rem; height: 2.8rem; }
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


def extract_legal_entity_name(text: str) -> str:
    """Extract a company name ending in a common Indian legal suffix."""
    normalized = re.sub(r"\s+", " ", text).strip()
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
        if x0 < width * 0.32 or y0 < height * 0.62 or y0 > height * 0.95:
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
    candidate_blocks = []

    for block in page.get_text("dict").get("blocks", []):
        lines = block.get("lines", [])
        if not lines:
            continue
        x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
        if x0 > width * 0.38 or x1 > width * 0.48:
            continue
        if y0 < height * 0.12 or y0 > height * 0.38:
            continue

        line_values = []
        max_size = 0.0
        for line in lines:
            line_text = " ".join(
                span.get("text", "").strip()
                for span in line.get("spans", [])
                if span.get("text", "").strip()
            )
            if not line_text:
                continue
            line_size = max(
                (span.get("size", 0.0) for span in line.get("spans", [])),
                default=0.0,
            )
            max_size = max(max_size, line_size)
            line_values.append((line_text, line_size))

        if line_values:
            candidate_blocks.append((max_size, y0, line_values))

    if not candidate_blocks:
        return ""

    _max_size, _y0, best_lines = max(
        candidate_blocks,
        key=lambda candidate: (candidate[0], -candidate[1]),
    )
    prominent_size = max(size for _text, size in best_lines)
    title_lines = [
        text
        for text, size in best_lines
        if size >= max(10.0, prominent_size * 0.78)
    ]
    return " ".join(title_lines).strip()


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
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = len(doc)
        for i, page in enumerate(doc, start=1):
            legal_manager = get_lower_right_legal_manager(page)
            manager_raw = legal_manager or get_manager_name(page)
            title_raw = (
                get_upper_left_title(page) if legal_manager else get_page_title(page)
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

            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image_path = output_dir / filename
            pix.save(str(image_path))
            del pix
            thumbnail_pix = page.get_pixmap(
                matrix=fitz.Matrix(0.45, 0.45),
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
    finally:
        doc.close()

    return total_pages, results


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def output_zip_name(original_name: str) -> str:
    return f"{safe_name(Path(original_name).stem)}_images.zip"


def build_output_zip(output: dict, results: list[dict]) -> str:
    """Build or reuse a disk-backed ZIP containing the selected pages."""
    signature = ",".join(str(item["page"]) for item in results)
    zip_path = Path(output["working_dir"]) / "selected_images.zip"
    if output.get("zip_signature") == signature and zip_path.exists():
        return str(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as archive:
        for item in results:
            archive.write(
                item["image_path"],
                f"{item['folder']}/{item['filename']}",
            )
    output["zip_signature"] = signature
    return str(zip_path)


def page_selection_key(output: dict, output_index: int, page: int) -> str:
    batch_id = output.get("batch_id", "current")
    return f"keep_page_{batch_id}_{output_index}_{page}"


def selected_output(output: dict, output_index: int) -> dict:
    """Return an output copy containing only currently selected pages."""
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
    zip_path = (
        build_output_zip(output, kept_results) if kept_results else None
    )
    filtered = dict(output)
    filtered["results"] = kept_results
    filtered["zip_path"] = zip_path
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


def collect_converted_pngs(outputs: list[dict]) -> list[tuple[str, str]]:
    """Return selected PNG names and disk paths without copying file data."""
    images = []
    used_names = {}

    for output in outputs:
        if output["error"] is not None or not output["results"]:
            continue
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
            images.append((image_name, item["image_path"]))

    return images


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


def is_replaceable_drive_image(item: dict) -> bool:
    """Identify direct PNG/JPG files while excluding folders and other files."""
    mime_type = (item.get("mimeType") or "").casefold()
    if mime_type == "application/vnd.google-apps.folder":
        return False
    return mime_type in {"image/png", "image/jpeg"} or Path(
        item.get("name", "")
    ).suffix.casefold() in {".png", ".jpg", ".jpeg"}


def replace_drive_folder(service, folder_id: str, images: list[tuple[str, str]]):
    """Replace direct PNG/JPG files, with best-effort rollback on error."""
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
        if is_replaceable_drive_image(item)
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
        for image_name, image_path in images:
            media = MediaFileUpload(
                image_path,
                mimetype="image/png",
                resumable=False,
            )
            created = service.files().create(
                body={"name": image_name, "parents": [folder_id]},
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            uploaded_ids.append(created["id"])

        # All uploads succeeded; move only previous direct image files to Trash.
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

        images = collect_converted_pngs(outputs)
        if not images:
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
    images = collect_converted_pngs([output])
    if not images:
        return

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
            f"This will move all PNG/JPG files directly inside "
            f"“{selected_folder_name}” to Drive Trash, then upload {len(images)} "
            "new PNGs. Non-image files and nested folders will remain untouched."
        )
        confirmed = st.checkbox(
            f"Replace the existing images in “{selected_folder_name}”.",
            key=f"drive_sync_confirm_{output_index}",
        )
        sync_clicked = st.button(
            f"Replace folder with {len(images)} PNGs",
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
                        images,
                    )
                except Exception as exc:
                    st.error(f"Drive sync failed: {exc}")
                else:
                    st.success(
                        f"Synced {uploaded_count} PNGs to “{folder_name}”. "
                        f"Moved {removed_count} previous image files to Trash."
                    )


st.markdown(
    """
    <div class="app-hero">
        <div class="app-mark">PNG</div>
        <div>
            <h1>PDF page exporter</h1>
            <p>Convert every PDF page to a crisp PNG, review what you want to keep, then download or sync only your final selection.</p>
        </div>
    </div>
    <div class="workflow-note" aria-label="Conversion steps">
        <span><strong>1.</strong> Select one or more PDFs</span>
        <span><strong>2.</strong> Delete unwanted images</span>
        <span><strong>3.</strong> Download or sync the pages you keep</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Upload PDFs")
st.caption("Select multiple files in one go. Each PDF is processed independently.")
st.info(
    "**Every page is converted.** The app supports both one-pager layouts and "
    "names portfolio pages `Smallcase by Manager`; all other pages use their "
    "detected page title. After conversion, use the bin button to remove images "
    "you do not want."
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
        options=[1.0, 1.5, 2.0, 2.5, 3.0],
        value=1.5,
        format_func=lambda value: {
            1.0: "Standard",
            1.5: "Balanced",
            2.0: "High",
            2.5: "Very high",
            3.0: "Maximum",
        }[value],
        help=(
            "Balanced is recommended for speed. Higher resolutions create "
            "sharper PNGs but take longer and use substantially more memory."
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

if "conversion_outputs" not in st.session_state:
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
            total_pages, results = convert_pdf_bytes(
                uploaded.getvalue(),
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
        "Download every PDF separately, or download one master ZIP containing "
        "all the individual ZIP files."
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

    summary_col, batch_download_col = st.columns(
        [1.7, 1],
        vertical_alignment="center",
    )
    with summary_col:
        if successful_outputs:
            st.success(
                f"Finished {successful_outputs} of "
                f"{len(st.session_state.conversion_outputs)} PDF files."
            )
    with batch_download_col:
        if len(downloadable_outputs) > 1:
            batch_zip_path = create_batch_zip(downloadable_outputs)
            with open(batch_zip_path, "rb") as batch_zip_file:
                st.download_button(
                    label=f"Download all {len(downloadable_outputs)} ZIPs",
                    data=batch_zip_file,
                    file_name="all_pdf_image_zips.zip",
                    mime="application/zip",
                    key="download_all_zips",
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

            result_col, download_col, drive_col = st.columns(
                [1.7, 0.8, 0.8],
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
            with download_col:
                zip_name = output_zip_name(output["original_name"])
                if converted_count:
                    with open(output["zip_path"], "rb") as zip_file:
                        st.download_button(
                            label="Download ZIP",
                            data=zip_file,
                            file_name=zip_name,
                            mime="application/zip",
                            key=f"download_{output_index}_{zip_name}",
                            use_container_width=True,
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
