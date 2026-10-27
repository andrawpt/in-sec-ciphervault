import html
import re
import zipfile
from pathlib import Path

MAX_XML_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 200_000

TEXT_EXTRACT_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
}
INLINE_MIMES = {"application/pdf", "image/jpeg", "image/png", "text/plain", "message/rfc822",
                "video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}


class PreviewUnavailable(Exception):
    pass


def _read(z: zipfile.ZipFile, name: str, budget: list[int]) -> str:
    info = z.getinfo(name)
    budget[0] -= info.file_size
    if budget[0] < 0:
        raise PreviewUnavailable("Document is too large for text preview")
    return z.read(name).decode("utf-8", errors="replace")


def _strip(xml: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _docx(z, budget):
    xml = _read(z, "word/document.xml", budget)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    paras = re.split(r"</w:p>", xml)
    return "\n".join(_strip(p) for p in paras).strip()


def _odt(z, budget):
    xml = _read(z, "content.xml", budget)
    xml = re.sub(r"<text:tab/>", "\t", xml)
    xml = re.sub(r"</text:(p|h)>", "\n", xml)
    return _strip(xml).strip()


def _pptx(z, budget):
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    out = []
    for i, name in enumerate(slides, 1):
        texts = [html.unescape(t) for t in re.findall(r"<a:t>(.*?)</a:t>", _read(z, name, budget), re.S)]
        out.append(f"--- Slide {i} ---\n" + "\n".join(texts))
    return "\n\n".join(out)


def _xlsx(z, budget):
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in re.findall(r"<si>(.*?)</si>", _read(z, "xl/sharedStrings.xml", budget), re.S):
            shared.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    sheets = sorted((n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    out = []
    for i, name in enumerate(sheets, 1):
        lines = [f"--- Sheet {i} ---"]
        for row in re.findall(r"<row[^>]*>(.*?)</row>", _read(z, name, budget), re.S):
            cells = []
            for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                inline = re.findall(r"<t[^>]*>(.*?)</t>", body, re.S)
                if 't="s"' in attrs and v:
                    idx = int(v.group(1))
                    cells.append(shared[idx] if idx < len(shared) else "")
                elif inline:
                    cells.append(html.unescape("".join(inline)))
                elif v:
                    cells.append(html.unescape(v.group(1)))
            lines.append("\t".join(cells))
        out.append("\n".join(lines))
    return "\n\n".join(out)


EXTRACTORS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _docx,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": _xlsx,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": _pptx,
    "application/vnd.oasis.opendocument.text": _odt,
}


def extract_text(path: Path, mime: str) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            text = EXTRACTORS[mime](z, [MAX_XML_BYTES])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise PreviewUnavailable("Document content could not be read") from exc
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[... truncated ...]"
    return text or "(document contains no text)"
