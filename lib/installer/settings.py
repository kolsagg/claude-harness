"""settings.json derin birleştirme. Girdiler değiştirilmez, yeni nesne döndürülür."""
import json


def _hook_key(hook):
    if isinstance(hook, dict) and isinstance(hook.get("command"), str):
        return hook["command"]
    return json.dumps(hook, sort_keys=True, ensure_ascii=False)


def _event_keys(groups):
    keys = set()
    for group in groups:
        if isinstance(group, dict) and isinstance(group.get("hooks"), list):
            keys.update(_hook_key(h) for h in group["hooks"])
        else:
            keys.add(json.dumps(group, sort_keys=True, ensure_ascii=False))
    return keys


def merge_hook_groups(existing, incoming):
    """Kullanıcı gruplarını korur; komutu olay içinde zaten bulunan hook'u eklemez."""
    result = list(existing)
    present = _event_keys(existing)
    for group in incoming:
        if isinstance(group, dict) and isinstance(group.get("hooks"), list):
            fresh = [h for h in group["hooks"] if _hook_key(h) not in present]
            if not fresh:
                continue
            present.update(_hook_key(h) for h in fresh)
            result.append({**group, "hooks": fresh})
        else:
            key = json.dumps(group, sort_keys=True, ensure_ascii=False)
            if key not in present:
                present.add(key)
                result.append(group)
    return result


# Alt anahtar bazında birleştirilen sözlük anahtarları; diğer sözlükler tek değer sayılır
PER_KEY = ("env", "enabledPlugins", "extraKnownMarketplaces", "pluginConfigs", "modelSettings", "permissions")
# İzin kapatılınca (evet -> hayır) geri alınabilen, harness'in yazdığı değerler
PERMISSION_TOP = "skipDangerousModePermissionPrompt"


def _decide(current, key, value, prev):
    """write: yaz | same: zaten aynı | keep: kullanıcının değerini koru."""
    if key not in current:
        return "write"
    if current[key] == value:
        return "same"
    if key in prev and prev[key] == current[key]:
        return "write"  # harness'in yazdığından beri değişmemiş
    return "keep"


def _merge_hooks(existing, incoming):
    base = existing if isinstance(existing, dict) else {}
    merged = dict(base)
    for event, groups in incoming.items():
        old = base.get(event)
        merged[event] = merge_hook_groups(old, groups) if isinstance(old, list) and isinstance(groups, list) else groups
    return merged


def _merge_sub(current, incoming, prev, label):
    """Sözlük anahtarını alt anahtar bazında birleştirir: (yeni sözlük, yazılanlar, korunanlar)."""
    merged, written, kept = dict(current), {}, []
    for sub, value in incoming.items():
        if isinstance(value, list) and isinstance(merged.get(sub), list):
            merged[sub] = list(merged[sub]) + [i for i in value if i not in merged[sub]]
            continue
        verdict = _decide(merged, sub, value, prev)
        if verdict == "keep":
            kept.append(f"{label}.{sub}")
        else:
            merged[sub] = value
            # "same": değer kullanıcıdan da gelmiş olabilir; sahiplik yalnız önceden harness'inse
            if not isinstance(value, list) and (verdict == "write" or sub in prev):
                written[sub] = value
    return merged, written, kept


def _retire_permissions(result, written, prev):
    """İzin modu kapatıldı: harness'in yazdığı değer hâlâ duruyorsa kaldır, değilse koru."""
    kept = []
    if PERMISSION_TOP in prev:
        if result.get(PERMISSION_TOP) == prev[PERMISSION_TOP]:
            result.pop(PERMISSION_TOP)
        elif PERMISSION_TOP in result:
            kept.append(PERMISSION_TOP)
        written.pop(PERMISSION_TOP, None)
    prev_perm = prev.get("permissions") if isinstance(prev.get("permissions"), dict) else {}
    if "defaultMode" in prev_perm and isinstance(result.get("permissions"), dict):
        perm = dict(result["permissions"])
        if perm.get("defaultMode") == prev_perm["defaultMode"]:
            perm.pop("defaultMode")
            result["permissions"] = perm
            if not perm:
                result.pop("permissions")
        elif "defaultMode" in perm:
            kept.append("permissions.defaultMode")
        sub = dict(written.get("permissions", {}))
        sub.pop("defaultMode", None)
        written = {**written, "permissions": sub} if sub else {k: v for k, v in written.items() if k != "permissions"}
    return result, written, kept


def apply_settings(existing, incoming, prev_written, with_permissions=True):
    """Kullanıcı değerlerini koruyan birleştirme. Girdiler değiştirilmez.

    Döner: (yeni ayarlar, settingsWritten, korunan anahtarlar). Harness bir anahtarı yalnız yoksa ya da
    kullanıcı onu harness'in yazdığından beri değiştirmediyse yazar. hooks komut metnine göre eklenir.
    """
    prev = prev_written if isinstance(prev_written, dict) else {}
    result, written, kept = dict(existing), {}, []
    for key, value in incoming.items():
        current = result.get(key)
        if key == "hooks" and isinstance(value, dict):
            result[key] = _merge_hooks(current, value)
        elif key in PER_KEY and isinstance(value, dict) and (key not in result or isinstance(current, dict)):
            sub_prev = prev.get(key) if isinstance(prev.get(key), dict) else {}
            merged, sub_written, sub_kept = _merge_sub(current or {}, value, sub_prev, key)
            result[key] = merged
            kept += sub_kept
            if sub_written:
                written[key] = sub_written
        elif isinstance(value, list) and isinstance(current, list):
            result[key] = list(current) + [i for i in value if i not in current]
        else:
            verdict = _decide(result, key, value, prev)
            if verdict == "keep":
                kept.append(key)
            else:
                result[key] = value
                if not isinstance(value, list) and (verdict == "write" or key in prev):
                    written[key] = value
    for key, value in prev.items():  # bu turda gelmeyen eski kayıtlar korunur (izin geri alma için)
        if key not in written and key not in incoming and key != "hooks":
            written[key] = value
        elif key in written and key in PER_KEY and isinstance(value, dict):
            extra = {k: v for k, v in value.items() if k not in written[key] and k not in incoming.get(key, {})}
            written[key] = {**written[key], **extra}
    if not with_permissions:
        result, written, retired_kept = _retire_permissions(result, written, prev)
        kept += retired_kept
    return result, written, kept


def dump_settings(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_settings(raw):
    """Bayt dizisinden sözlük; geçersizse ValueError (dosyaya dokunulmaz)."""
    if raw is None:
        return {}
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"mevcut settings.json okunamadı: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("mevcut settings.json bir JSON nesnesi değil")
    return data
