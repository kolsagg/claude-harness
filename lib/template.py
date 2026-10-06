"""Ortak şablon motoru: yer tutucu, koşullu blok, private blok.

Yalnız stdlib. Girdi nesneleri değiştirilmez; her fonksiyon yeni değer döndürür.
"""
import re

KNOWN = ("USER_NAME", "HOME", "VAULT_PATH", "GITHUB_OWNER", "LANGUAGE", "PYTHON")
PLACEHOLDER = re.compile(r"\{\{(" + "|".join(KNOWN) + r")\}\}")
COND_OPEN = re.compile(r"^\s*<!-- if:([a-z]+) -->\s*$")
COND_CLOSE = re.compile(r"^\s*<!-- endif:([a-z]+) -->\s*$")
PRIVATE_OPEN = "<!-- private:start -->"
PRIVATE_CLOSE = "<!-- private:end -->"
REQUIRES_KEY = "_requires"


class UnresolvedPlaceholder(KeyError):
    pass


def _fill(text, values):
    def sub(match):
        name = match.group(1)
        if name not in values:
            raise UnresolvedPlaceholder(name)
        return values[name]

    return PLACEHOLDER.sub(sub, text)


def _apply_conditions(text, flags):
    out = []
    stack = []  # (koşul, tutulsun mu)
    for line in text.splitlines(keepends=True):
        opened = COND_OPEN.match(line)
        closed = COND_CLOSE.match(line)
        visible = all(keep for _, keep in stack)
        if opened:
            stack = stack + [(opened.group(1), opened.group(1) in flags)]
            if visible and stack[-1][1]:
                out.append(line)
            continue
        if closed:
            if not stack or stack[-1][0] != closed.group(1):
                raise ValueError(f"eşleşmeyen endif:{closed.group(1)}")
            keep = all(k for _, k in stack)
            stack = stack[:-1]
            if keep:
                out.append(line)
            continue
        if visible:
            out.append(line)
    if stack:
        raise ValueError(f"kapanmamış if:{stack[-1][0]}")
    return "".join(out)


def render_text(text, values, flags):
    """Koşulları uygula, sonra yer tutucuları doldur."""
    return _fill(_apply_conditions(text, flags), values)


def strip_private(text):
    out = []
    inside = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == PRIVATE_OPEN:
            if inside:
                raise ValueError("iç içe private blok")
            inside = True
            continue
        if stripped == PRIVATE_CLOSE:
            if not inside:
                raise ValueError("eşleşmeyen private:end")
            inside = False
            continue
        if not inside:
            out.append(line)
    if inside:
        raise ValueError("kapanmamış private blok")
    return "".join(out)


_DROP = object()


def _render_node(node, values, flags):
    if isinstance(node, dict):
        if REQUIRES_KEY in node:
            if node[REQUIRES_KEY] not in flags:
                return _DROP
            rest = {k: v for k, v in node.items() if k != REQUIRES_KEY}
            if set(rest) == {"value"}:
                return _render_node(rest["value"], values, flags)
            return _render_node(rest, values, flags)
        rendered = {k: _render_node(v, values, flags) for k, v in node.items()}
        return {k: v for k, v in rendered.items() if v is not _DROP}
    if isinstance(node, list):
        rendered = [_render_node(v, values, flags) for v in node]
        return [v for v in rendered if v is not _DROP]
    if isinstance(node, str):
        return _fill(node, values)
    return node


def render_json(data, values, flags):
    """JSON ağacını render et: `_requires` tutmayan elemanı düşür, yer tutucuları doldur."""
    return _render_node(data, values, flags)
