#!/usr/bin/env python3
"""Переносит длинные подписи и примечания в .puml, чтобы диаграммы не были «лентами».

Использование: python3 wrap_puml.py <папка с .puml> [max_chars]
Правит файлы на месте, идемпотентно (повторный запуск ничего не меняет).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ARROW = re.compile(
    r"^(?P<indent>\s*)(?P<left>[^\s:]+)\s*(?P<arrow>-{1,2}>|\.{2}>|<-{1,2}|o-+>|<--)\s*(?P<right>[^\s:]+)\s*:\s*(?P<label>.+?)\s*$"
)
NOTE_START = re.compile(r"^(?P<indent>\s*)(?P<kw>note\s+(?:over|left|right|top|bottom)\s+[^\s:]+)\s*(?::\s*(?P<inline>.+))?$")
NOTE_END = re.compile(r"^\s*end\s*note\s*$", re.I)


def wrap(text: str, limit: int) -> str:
    """Разбивает текст по словам на строки не длиннее limit, разделитель — \\n для PlantUML."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= limit:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\\n".join(lines)


def process(path: Path, limit: int) -> bool:
    src = path.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    changed = False
    in_note = False
    has_maxmsg = any("maxMessageSize" in l for l in src)

    for line in src:
        # 1. внутри многострочного примечания — переносим по словам
        if in_note:
            if NOTE_END.match(line):
                in_note = False
                out.append(line)
                continue
            stripped = line.strip()
            if len(stripped) > limit:
                indent = line[: len(line) - len(line.lstrip())]
                for part in wrap(stripped, limit).split("\\n"):
                    out.append(indent + part)
                changed = True
            else:
                out.append(line)
            continue

        # 2. начало примечания
        m = NOTE_START.match(line)
        if m:
            inline = m.group("inline")
            out.append(line if inline is None else f"{m.group('indent')}{m.group('kw')}")
            if inline is not None:
                changed = True
                if len(inline) > limit:
                    indent = m.group("indent") + "  "
                    for part in wrap(inline, limit).split("\\n"):
                        out.append(indent + part)
                else:
                    out.append(m.group("indent") + "  " + inline)
            if inline is not None or m.group("inline") is None:
                in_note = True
            continue

        # 3. подпись сообщения
        a = ARROW.match(line)
        if a and len(a.group("label")) > limit:
            new_label = wrap(a.group("label"), limit)
            out.append(f"{a.group('indent')}{a.group('left')} {a.group('arrow')} {a.group('right')} : {new_label}")
            changed = True
            continue

        out.append(line)

    # 4. добавляем maxMessageSize, если его нет (только для sequence-диаграмм)
    text = "\n".join(out)
    if "sequenceDiagram" in text or "->>" in text or re.search(r"^\s*\w+\s*->\s*\w+\s*:", text, re.M):
        if not has_maxmsg:
            text = re.sub(r"(?m)^(skinparam defaultFontName[^\n]*)$",
                          r"\1\nskinparam maxMessageSize %d" % limit, text, count=1)
            if "maxMessageSize" not in text:
                text = re.sub(r"(?m)^(title[^\n]*)$",
                              r"\1\nskinparam maxMessageSize %d" % limit, text, count=1)
            changed = True

    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    folder = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    files = sorted(folder.glob("*.puml"))
    n = 0
    for f in files:
        if process(f, limit):
            n += 1
            print("правлен:", f.name)
    print(f"итого изменено {n} из {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
