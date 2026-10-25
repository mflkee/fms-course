"""Минимальный генератор PDF для выгрузки реестра (без внешних зависимостей).

Ограничение учебной реализации: шрифт не встраивается, поэтому кириллица
транслитерируется латиницей — иначе встроенный Helvetica её не отобразит.
Для полноценного PDF нужен движок со встроенным шрифтом (см. README,
раздел «Ограничения»).
"""

from __future__ import annotations

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    result: list[str] = []
    for char in text:
        lowered = char.lower()
        if lowered in _TRANSLIT:
            replacement = _TRANSLIT[lowered]
            result.append(replacement.upper() if char.isupper() else replacement)
        else:
            result.append(char)
    return "".join(result)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(line: str, width: int = 110) -> list[str]:
    return [line[index : index + width] for index in range(0, max(len(line), 1), width)]


def render_pdf(*, title: str, lines: list[str], max_lines: int = 55) -> bytes:
    """Собрать одностраничный PDF с заголовком и строками текста."""
    printable: list[str] = [transliterate(title), ""]
    for line in lines:
        printable.extend(transliterate(line).splitlines() or [""])
    if len(printable) > max_lines:
        printable = printable[: max_lines - 1] + ["... (truncated)"]

    parts = ["BT", "/F1 9 Tf", "14 TL", "40 800 Td"]
    for line in printable:
        parts.append(f"({_escape(line)}) Tj T*")
    parts.append("ET")
    stream = "\n".join(parts).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    document = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode()
    document += b"0000000000 65535 f \n"
    for offset in offsets:
        document += f"{offset:010d} 00000 n \n".encode()
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(document)
