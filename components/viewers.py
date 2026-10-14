"""In-app file viewers so learners can read content without downloading it.

PDFs are shown as extracted text; images render inline; text/HTML renders inline; interactive HTML
activities run in a sandboxed iframe; anything else falls back to a download.
"""
import base64
import io
import html as _html

import streamlit as st
import streamlit.components.v1 as components

from services.files import extension_of, INLINE_IMAGE, INLINE_PDF, INLINE_TEXT


def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


@st.cache_data(show_spinner=False, max_entries=64)
def _pdf_to_images(data: bytes, dpi: int = 150, max_pages: int = 40) -> list[bytes]:
    """Render PDF pages to PNG bytes, preserving the document's real layout, headings and colours."""
    try:
        import pymupdf
        doc = pymupdf.open(stream=data, filetype="pdf")
        out = []
        for i in range(min(doc.page_count, max_pages)):
            out.append(doc[i].get_pixmap(dpi=dpi).tobytes("png"))
        return out
    except Exception:
        return []


def _pdf_to_text(data: bytes) -> str:
    """Extract readable text from a PDF. Returns '' if the PDF has no extractable text."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            t = (page.extract_text() or "").strip()
            if t:
                pages.append(t)
        return "\n\n".join(pages).strip()
    except Exception:
        return ""


def _reflow(text: str) -> str:
    """Merge lines that are obviously a wrapped sentence, so extracted PDF text reads as paragraphs
    while headings and list items keep their own line."""
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue
        if (out and out[-1] and not out[-1].endswith((".", ":", "!", "?", ";"))
                and line[:1].islower()):
            out[-1] = out[-1] + " " + line
        else:
            out.append(line)
    return "\n".join(out)


def _render_text_block(text: str, height: int = 560) -> None:
    """Render plain text as a readable, scrollable block (preserving paragraphs)."""
    safe = _html.escape(text)
    # Collapse 3+ newlines, turn blank-line gaps into paragraph breaks, single newlines into <br>.
    paras = [p.strip() for p in safe.replace("\r\n", "\n").split("\n\n") if p.strip()]
    body = "".join(f"<p style='margin:0 0 10px'>{p.replace(chr(10), '<br>')}</p>" for p in paras)
    st.markdown(
        f'<div style="max-height:{height}px;overflow:auto;border:1px solid #d9e0e6;border-radius:10px;'
        f'padding:16px 18px;background:#ffffff;font-size:14px;line-height:1.55;color:#13293d">{body}</div>',
        unsafe_allow_html=True,
    )


def embed_file(file_name: str, data: bytes, mime: str, *, height: int = 640,
               download_label: str = "Download file") -> None:
    """Render a file inline where the format allows; otherwise offer a download fallback."""
    ext = extension_of(file_name)
    mime = mime or "application/octet-stream"

    # PDFs are shown as their actual page images (faithful layout, headings and colours), which
    # works on every browser. Falls back to extracted text, then to a download.
    if ext in INLINE_PDF or mime == "application/pdf":
        images = _pdf_to_images(data)
        if images:
            for png in images:
                st.image(png, use_container_width=True)
            return
        text = _pdf_to_text(data)
        if text:
            _render_text_block(_reflow(text), height=min(height, 620))
        else:
            st.info("This PDF has no extractable content (it may be encrypted). Use the link below.")
            st.download_button(download_label, data=data, file_name=file_name, mime=mime)
        return

    if ext in INLINE_IMAGE or mime.startswith("image/"):
        st.image(data, use_container_width=True)
        return

    if ext in ("html", "htm"):
        # Interactive HTML learning activities run inside a sandboxed iframe. "allow-scripts" lets
        # the activity's own JavaScript run; the absence of "allow-same-origin" keeps it in an opaque
        # origin, isolated from the app, its cookies and its storage. A single internal scrollbar is
        # kept (the outer component does not scroll) so the view is not doubly scrolled.
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        h = max(height, 760)
        components.html(
            f'<iframe srcdoc="{_html.escape(text, quote=True)}" '
            f'sandbox="allow-scripts allow-popups allow-forms" '
            f'style="width:100%;height:{h}px;border:1px solid #d9e0e6;border-radius:10px;display:block"></iframe>',
            height=h + 6, scrolling=False,
        )
        return

    if ext in INLINE_TEXT or mime.startswith("text/"):
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        _render_text_block(text, height=min(height, 560))
        return

    # Fallback: cannot render this format in the browser.
    st.info("This file format cannot be displayed in the browser. Use the link below to open it.")
    st.download_button(download_label, data=data, file_name=file_name, mime=mime)
