"""Interactive Google Form filler.

Prompts for a form URL, shows detected fields, asks what to fill for each field,
and submits the form multiple times with the same payload.
"""

from __future__ import annotations

import json
from typing import Any

import requests

import form


def _describe_field(entry: dict[str, Any], index: int) -> None:
    label = entry["container_name"]
    if entry.get("name"):
        label += f" - {entry['name']}"

    required_label = "required" if entry.get("required") else "optional"
    print(f"{index}. {label} [{required_label}] (id: {entry['id']})")

    if entry.get("default_value") is not None:
        print(f"   default value: {entry['default_value']}")

    options = entry.get("options")
    if options:
        print(f"   options: {options}")


def _prompt_value(entry: dict[str, Any]) -> Any:
    # Keep auto-generated values (e.g. pageHistory) unless user overrides later.
    if entry.get("default_value") is not None:
        return entry["default_value"]

    label = entry["container_name"]
    if entry.get("name"):
        label += f" - {entry['name']}"

    options = entry.get("options") or []
    required = bool(entry.get("required"))
    field_type = entry.get("type")
    allow_custom_value = form.ANY_TEXT_FIELD in options

    while True:
        if options and field_type == 4:
            raw = input(
                f"Value for '{label}' (checkboxes, comma-separated values): "
            ).strip()
        elif options:
            raw = input(f"Value for '{label}' (pick one option): ").strip()
        else:
            raw = input(f"Value for '{label}': ").strip()

        if not raw:
            if required:
                print("This field is required. Please enter a value.")
                continue
            if field_type == 4:
                return []
            return ""

        if not options:
            return raw

        allowed_options = [opt for opt in options if opt != form.ANY_TEXT_FIELD]

        if field_type == 4:
            selected = [value.strip() for value in raw.split(",") if value.strip()]
            if not selected and required:
                print("Please choose at least one value.")
                continue
            invalid = [value for value in selected if value not in allowed_options]
            if invalid and not allow_custom_value:
                print(f"Invalid options: {invalid}. Please choose from {allowed_options}")
                continue
            return selected

        if raw in allowed_options or allow_custom_value:
            return raw

        print(f"Invalid option. Please choose from {allowed_options}")


def _build_payload(entries: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for entry in entries:
        value = entry["value"]
        if entry.get("type") == "required":
            key = entry["id"]
        else:
            key = f"entry.{entry['id']}"
        payload[key] = value
    return payload


def _ask_submission_count() -> int:
    while True:
        raw = input("How many times should it submit this payload? ").strip()
        try:
            count = int(raw)
        except ValueError:
            print("Please enter a whole number (example: 3)")
            continue

        if count <= 0:
            print("Please enter a number greater than 0")
            continue
        return count


def main() -> None:
    url = input("Paste Google Form URL: ").strip()
    if not url:
        print("No URL provided.")
        return

    entries = form.parse_form_entries(url)
    if not entries:
        print("Could not parse form fields from that URL.")
        return

    print("\nDetected form fields:")
    for i, entry in enumerate(entries, start=1):
        _describe_field(entry, i)

    print("\nEnter values for each field:")
    for entry in entries:
        entry["value"] = _prompt_value(entry)

    payload = _build_payload(entries)
    print("\nPayload to submit:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    submit_count = _ask_submission_count()
    response_url = form.get_form_response_url(url)

    success = 0
    failed = 0
    for attempt in range(1, submit_count + 1):
        try:
            res = requests.post(response_url, data=payload, timeout=10)
            if res.status_code == 200:
                success += 1
                print(f"[{attempt}/{submit_count}] Submitted successfully")
            else:
                failed += 1
                print(f"[{attempt}/{submit_count}] Failed with status {res.status_code}")
        except requests.RequestException as exc:
            failed += 1
            print(f"[{attempt}/{submit_count}] Failed with error: {exc}")

    print(f"\nDone. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
