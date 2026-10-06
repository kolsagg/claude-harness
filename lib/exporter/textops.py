"""Metin hattı: strip_private -> replace; ikili dosya tespiti; glob eşleme."""
import re

from lib.template import strip_private


def decode_text(data):
    """Bayt dizisi metinse str, değilse None döndür."""
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def apply_replace(text, pairs):
    for src, dst in pairs:
        text = text.replace(src, dst)
    return text


def transform_text(text, pairs):
    """Önce private blokları sil, sonra eşlemeleri sırayla uygula."""
    return apply_replace(strip_private(text), pairs)


def normalize_newlines(data):
    """Metin dosyalarda CRLF -> LF; ikili dosyaya dokunma."""
    text = decode_text(data)
    if text is None:
        return data
    return text.replace("\r\n", "\n").encode("utf-8")


def transform_bytes(data, pairs):
    text = decode_text(data)
    if text is None:
        return data
    # Satır sonları LF'e normalize edilir: .gitattributes eol=lf, MANIFEST hash'i tutsun
    text = text.replace("\r\n", "\n")
    return transform_text(text, pairs).encode("utf-8")


def _glob_regex(pattern):
    # ** birden çok dizin, * tek dizin içinde
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def is_excluded(rel_path, patterns):
    rel = rel_path.replace("\\", "/")
    return any(_glob_regex(p).match(rel) for p in patterns)
