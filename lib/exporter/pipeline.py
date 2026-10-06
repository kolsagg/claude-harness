"""Export akışı: build -> manifest -> scrub -> atomik yazma."""
import json
import shutil
import tempfile
from pathlib import Path

from .build import ExportError, build_payload, manifest_bytes
from .config import ConfigError, load_harness, load_local_config
from .scrub import apply_allow, parse_allow, read_extra_docs, scrub_files
from .settings import UnknownHookError
from .tree import read_tree

SECTIONS = ("global", "skills", "settings", "codex")


def _load_lock(root):
    path = Path(root) / "overrides.lock"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_allow(root):
    path = Path(root) / "scrub-allow.txt"
    if not path.is_file():
        return []
    return parse_allow(path.read_text(encoding="utf-8"))


def read_payload_dir(out):
    out = Path(out)
    if not out.is_dir():
        raise ExportError(f"payload dizini yok: {out}")
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def _scrub(files, root, local, allow):
    """(bulgular, kullanılmayan allow girdileri); yazdırmaz."""
    pool = {**files, **read_extra_docs(root)}
    return apply_allow(scrub_files(pool, local), allow)


def _scrub_tree(root, out, local, allow):
    """Git ağacının tamamını tara. payload/ zaten --out taramasında; aynı dizinse atlanır."""
    skip = ("payload/",) if Path(out).resolve() == (Path(root) / "payload").resolve() else ()
    return apply_allow(scrub_files(read_tree(root, skip), local), allow)


def _report(say, scans, tree_ran):
    """Birden çok taramanın bulgularını yinelenmeden yaz; allow girdisi hiçbirinde kullanılmadıysa uyar."""
    unused = set(scans[0][1])
    for _f, u in scans[1:]:
        unused &= set(u)
    # Ağaç taranmadıysa allow girdilerinin bir kısmı yalnız ağaçta kullanılır; uyarı yanıltıcı olur
    for entry in sorted(unused if tree_ran else ()):
        say(f"uyarı: kullanılmayan allow girdisi: {':'.join(entry)}")
    seen, out = set(), []
    for findings, _u in scans:
        for f in findings:
            if f.render() not in seen:
                seen.add(f.render())
                out.append(f)
                say(f.render())
    return out


def write_atomic(files, out):
    """Geçici dizine yaz, eski payload'u yedekleyip yerine koy; hata olursa eskiyi geri al."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".payload-new-", dir=out.parent))
    backup = out.parent / (out.name + ".old")
    try:
        for rel, data in files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if backup.exists():
            shutil.rmtree(backup)
        if out.exists():
            out.rename(backup)
        try:
            tmp.rename(out)
        except OSError:
            if backup.exists():
                backup.rename(out)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def _counts(files):
    counts = {s: sum(1 for p in files if p.startswith(s + "/")) for s in SECTIONS}
    counts["manifest"] = 1 if "MANIFEST.json" in files else 0
    return counts


def run_export(root, source_home, out, local_path, check_only, say=print, tree=False):
    """Çıkış kodu döndür: 0 temiz, 1 scrub/hook hatası, 2 yapılandırma hatası."""
    try:
        local = load_local_config(local_path)
        harness = load_harness(root)
        allow = _load_allow(root)
        lock = _load_lock(root)
        for w in local.warnings:
            say(f"uyarı: {w}")
        if tree and not check_only:
            found = _report(say, [_scrub_tree(root, out, local, allow)], True)
            say(f"tree: {len(found)} bulgu")
            return 1 if found else 0
        if check_only:
            files = read_payload_dir(out)
            scans = [_scrub(files, root, local, allow)]
            if tree:
                scans.append(_scrub_tree(root, out, local, allow))
            found = _report(say, scans, tree)
            say(f"check-only: {len(files)} dosya, {len(found)} bulgu")
            return 1 if found else 0
        files, warnings = build_payload(source_home, harness, local, Path(root) / "overrides", lock)
    except UnknownHookError as exc:
        say("HATA: hookRules'ta sınıflandırılmamış hook komutları (harness.json'a kural ekleyin):")
        for c in exc.commands:
            say(f"  {c}")
        return 1
    except (ConfigError, ExportError, ValueError) as exc:
        say(f"HATA: {exc}")
        return 2
    for w in warnings:
        say(f"uyarı: {w}")
    files = {**files, "MANIFEST.json": manifest_bytes(files)}
    payload_scan = _scrub(files, root, local, allow)
    if payload_scan[0]:
        _report(say, [payload_scan], False)
        say(f"scrub BAŞARISIZ: {len(payload_scan[0])} bulgu; payload değiştirilmedi")
        return 1
    write_atomic(files, out)
    counts = _counts(files)
    say("export tamam: " + ", ".join(f"{k}={v}" for k, v in counts.items()) + f", toplam={len(files)}")
    say("scrub: 0 bulgu")
    # Payload yazıldıktan sonra tüm git ağacı da temiz olmalı (public push öncesi kanıt)
    try:
        tree_scan = _scrub_tree(root, out, local, allow)
    except ExportError as exc:
        say(f"HATA: {exc}")
        return 2
    found = _report(say, [payload_scan, tree_scan], True)
    if found:
        say(f"ağaç scrub BAŞARISIZ: {len(found)} bulgu (payload yazıldı)")
        return 1
    return 0
