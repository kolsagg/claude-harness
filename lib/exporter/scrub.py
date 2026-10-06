"""Scrub: payload ve repo belgelerinde kişisel veri / sır taraması."""
import re
from dataclasses import dataclass
from pathlib import Path

from .textops import decode_text, is_excluded

CONTEXT = 24  # eşleşmenin iki yanında gösterilen karakter sayısı

_ABS_USER = r"(?!\{\{)[^\\/\s\"'`]+"
RULES = (
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"), False),
    ("token-sk", re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}"), True),
    ("token-gh", re.compile(r"\bgh[po]_[A-Za-z0-9]{10,}"), True),
    ("token-slack", re.compile(r"\bxox[A-Za-z]?-?[A-Za-z0-9\-]{8,}"), True),
    ("token-aws", re.compile(r"\bAKIA[0-9A-Z]{12,}"), True),
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=\-]{20,}"), True),
    ("api-key", re.compile(r"api[_-]?key\s*[:=]\s*\S{8,}", re.IGNORECASE), True),
    ("abs-path", re.compile(
        r"(?:[A-Za-z]:[\\/]+Users[\\/]+" + _ABS_USER + r"|/[A-Za-z]/Users/" + _ABS_USER
        + r"|/Users/" + _ABS_USER + r"/|/home/" + _ABS_USER + r"/)"
    ), False),
)
EXTRA_DOCS = ("harness.json", "README.md", "INSTALL.md")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    excerpt: str  # yazdırılan (gerekirse maskeli)
    context: str  # allow-list eşleşmesi için ham bağlam

    def render(self):
        return f"{self.path}:{self.line}: {self.rule}: {self.excerpt}"


def _context(line, start, end):
    return line[max(0, start - CONTEXT):end + CONTEXT].strip()


def _make(path, lineno, rule, line, match, mask):
    raw = _context(line, match.start(), match.end())
    shown = raw
    if mask:
        text = match.group(0)
        shown = raw.replace(text, text[:6] + "***", 1)
    return Finding(path, lineno, rule, shown, raw)


_WORD_CHAR = r"A-Za-z0-9_"


def forbidden_pattern(word):
    """Yasaklı kelime kuralı (iki yerde aynı: metin ve ikili tarama).

    Baş harfi büyük girdi (Foo, Bar): tam kelime + büyük/küçük harfe duyarlı;
    böylece kabuk `echo` ya da "makes sense" yanlış pozitif vermez.
    Küçük harfle başlayan girdi (foo, foo.example): alt metin + duyarsız.
    """
    esc = re.escape(word)
    if word[0].isupper():
        return rf"(?<![{_WORD_CHAR}]){esc}(?![{_WORD_CHAR}])", 0
    return esc, re.IGNORECASE


def _forbidden_regexes(local):
    return [re.compile(*forbidden_pattern(w)) for w in local.forbidden if w]


def _scan_text(path, text, local):
    findings = []
    forb = [(None, rx) for rx in _forbidden_regexes(local)]
    for lineno, line in enumerate(text.splitlines(), 1):
        for word, rx in forb:
            for m in rx.finditer(line):
                findings.append(_make(path, lineno, "forbidden", line, m, False))
        for src, _dst in local.replace:
            if not src:
                continue
            for m in re.finditer(re.escape(src), line):
                findings.append(_make(path, lineno, "replace-from", line, m, False))
        for rule, rx, mask in RULES:
            for m in rx.finditer(line):
                findings.append(_make(path, lineno, rule, line, m, mask))
    return findings


def _scan_binary(path, data, local):
    out = []
    for w in local.forbidden:
        if not w:
            continue
        pat, flags = forbidden_pattern(w)
        if re.search(pat.encode("utf-8"), data, flags):
            out.append(Finding(path, 0, "forbidden-binary", f"{w} (ikili dosya)", w))
    return out


def scrub_files(files, local):
    """files: yol -> bayt. Bulguları (yol, satır) sırasıyla döndür."""
    findings = []
    for path in sorted(files):
        text = decode_text(files[path])
        if text is None:
            findings.extend(_scan_binary(path, files[path], local))
        else:
            findings.extend(_scan_text(path, text, local))
    return findings


def read_extra_docs(root):
    out = {}
    for name in EXTRA_DOCS:
        p = Path(root) / name
        if p.is_file():
            out[name] = p.read_bytes()
    return out


def parse_allow(text):
    """Satır: `yol:kural:alt-metin  # gerekçe`. Gerekçesiz satır ValueError."""
    entries = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body, sep, reason = line.partition(" #")
        if not sep or not reason.strip():
            raise ValueError(f"scrub-allow.txt:{n}: gerekçe yorumu (# ...) eksik")
        parts = body.strip().split(":", 2)
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"scrub-allow.txt:{n}: biçim yol:kural:alt-metin olmalı")
        entries.append(tuple(parts))
    return entries


def _path_matches(pattern, path):
    # Yol tam eşleşir ya da glob'dur (tests/** gibi); virgülle birden çok yol verilebilir
    return any(
        pat == path or ("*" in pat and is_excluded(path, [pat]))
        for pat in pattern.split(",")
    )


def apply_allow(findings, entries):
    """(kalan_bulgular, kullanılmayan_allow_girdileri) döndür."""
    used = set()
    remaining = []
    for f in findings:
        hit = next(
            (e for e in entries if _path_matches(e[0], f.path) and e[1] == f.rule and e[2] in f.context),
            None,
        )
        if hit is None:
            remaining.append(f)
        else:
            used.add(hit)
    return remaining, [e for e in entries if e not in used]
