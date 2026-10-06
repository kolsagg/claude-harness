"""Global CLAUDE.md: yönetilen blok işaretleri arasında birleştirme."""

START = "<!-- claude-harness:start -->"
END = "<!-- claude-harness:end -->"


def _block(rendered):
    return f"{START}\n{rendered.strip(chr(10))}\n{END}"


def merge_claude_md(existing, rendered):
    """existing None ise yeni dosya. İşaret yoksa blok üste, eski içerik altına gider."""
    block = _block(rendered)
    if existing is None or not existing.strip():
        return block + "\n"
    s = existing.find(START)
    if s == -1:
        return block + "\n\n" + existing
    e = existing.find(END, s + len(START))
    if e == -1:
        raise ValueError("CLAUDE.md'de claude-harness:start var ama end yok; elle düzeltin")
    return existing[:s] + block + existing[e + len(END):]
