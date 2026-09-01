#!/usr/bin/env python3
"""Создаёт authorized_key.json из секрета GitHub Actions (JSON или base64)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

REQUIRED = frozenset({"id", "service_account_id", "private_key"})
OUTPUT = "authorized_key.json"


def _normalize(text: str) -> str:
    text = text.strip().lstrip("\ufeff")
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _unwrap_github_tojson(value: str) -> str:
    """Разворачивает значение, переданное через toJSON(secrets.*) в workflow."""
    value = value.strip()
    if not value:
        return value
    try:
        unwrapped = json.loads(value)
    except json.JSONDecodeError:
        return value
    if isinstance(unwrapped, str):
        return unwrapped
    if isinstance(unwrapped, dict):
        return json.dumps(unwrapped, ensure_ascii=False)
    return value


def _validate_key(obj: object) -> dict:
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict):
        raise ValueError("ожидается JSON-объект authorized_key.json")
    missing = REQUIRED - obj.keys()
    if missing:
        raise ValueError("нет обязательных полей: " + ", ".join(sorted(missing)))
    if not str(obj.get("private_key", "")).strip():
        raise ValueError("поле private_key пустое")
    return obj


def _try_json(text: str) -> dict | None:
    try:
        return _validate_key(json.loads(text))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _try_base64_json(text: str) -> dict | None:
    try:
        blob = re.sub(r"[^A-Za-z0-9+/=_-]", "", text)
        if len(blob) < 16:
            return None
        pad = (-len(blob)) % 4
        decoded = base64.b64decode(blob + "=" * pad, validate=False).decode("utf-8")
        return _validate_key(json.loads(decoded))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None


def _try_relaxed_json(text: str) -> dict | None:
    """JSON, испорченный при копировании (экранирование, literal \\n)."""
    variants = [text]
    if "\\n" in text and "\n" not in text[:500]:
        variants.append(text.replace("\\n", "\n").replace("\\r", "\r"))
    if '\\"' in text:
        variants.append(text.replace('\\"', '"'))

    for variant in variants:
        key = _try_json(variant)
        if key is not None:
            return key
    return None


def _collect_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def add(name: str, value: str | None) -> None:
        if not value or not value.strip():
            return
        candidates.append((name, value))

    add("YC_SERVICE_ACCOUNT_KEY_B64", os.environ.get("SA_KEY_B64"))
    add("SA_KEY_JSON (toJSON)", _unwrap_github_tojson(os.environ.get("SA_KEY_JSON", "")))

    for name in (
        "SA_KEY",
        "YC_SERVICE_ACCOUNT_KEY_FILE",
        "YC_SERVICE_ACCOUNT_KEY",
    ):
        add(name, os.environ.get(name))

    path = os.environ.get("SA_KEY_FILE")
    if path and os.path.isfile(path):
        add(f"file:{path}", open(path, encoding="utf-8").read())

    # убрать дубликаты по содержимому
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, value in candidates:
        norm = _normalize(value)
        if norm and norm not in seen:
            seen.add(norm)
            unique.append((label, value))
    return unique


def _diagnose(candidates: list[tuple[str, str]]) -> None:
    print("::group::Диагностика секрета (значения не показываются)")
    if not candidates:
        print("  ⚠ Ни один источник ключа не передан в окружение.")
    for label, raw in candidates:
        raw = _normalize(raw)
        preview = raw[:24].replace("\n", "\\n").replace("\r", "\\r")
        print(f"  [{label}] длина={len(raw)}, строк={raw.count(chr(10)) + 1}, "
              f"starts_with_brace={raw.startswith('{')}, preview={preview!r}...")
        if raw.startswith("***"):
            print("    ⚠ Похоже на маску GitHub (***) из лога, не на ключ.")
        first = raw.split()[0] if raw.split() else ""
        if re.match(r"^YCA[A-Za-z0-9]+$", first):
            print("    ⚠ Похоже на статический ключ YCA..., не authorized_key.json.")
        if raw.startswith("AQVN"):
            print("    ⚠ Похоже на IAM-токен.")
        if "BEGIN PRIVATE KEY" in raw and not raw.strip().startswith("{"):
            print("    ⚠ Только PEM без JSON-обёртки.")
    print("::endgroup::")


def parse_sa_key(raw: str) -> tuple[dict, str]:
    raw = _normalize(raw)
    if not raw:
        raise ValueError("пустое значение")

    parsers: list[tuple[str, object]] = [
        ("JSON", _try_json),
        ("relaxed JSON", _try_relaxed_json),
        ("base64(JSON)", _try_base64_json),
    ]

    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        parsers.extend(
            [
                (f"JSON в {raw[0]!r}", lambda _: _try_json(inner)),
                (f"relaxed JSON в {raw[0]!r}", lambda _: _try_relaxed_json(inner)),
                (f"base64(JSON) в {raw[0]!r}", lambda _: _try_base64_json(inner)),
            ]
        )

    for fmt_label, parser in parsers:
        key = parser(raw)
        if key is not None:
            return key, fmt_label

    raise ValueError("не удалось разобрать ключ")


def write_key(obj: dict, path: str = OUTPUT) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только проверить, не создавать authorized_key.json",
    )
    args = parser.parse_args()

    candidates = _collect_candidates()
    errors: list[str] = []

    for label, raw in candidates:
        try:
            key, fmt = parse_sa_key(raw)
            if not args.dry_run:
                write_key(key)
            print(f"OK: ключ из {label} (формат: {fmt})")
            return 0
        except ValueError as exc:
            errors.append(f"{label}: {exc}")

    _diagnose(candidates)
    print("::error::Не удалось разобрать ключ сервисного аккаунта.", file=sys.stderr)
    for err in errors:
        print(f"::error::  {err}", file=sys.stderr)
    print(
        "::error::Создайте ключ: Yandex Cloud → IAM → Сервисные аккаунты → "
        "Создать ключ → JSON. Затем на своём ПК:\n"
        "  gh secret set YC_SERVICE_ACCOUNT_KEY_B64 "
        '--body "$(base64 -w0 authorized_key.json)"\n'
        "  # или:\n"
        "  gh secret set YC_SERVICE_ACCOUNT_KEY_FILE "
        "--body-file authorized_key.json",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
