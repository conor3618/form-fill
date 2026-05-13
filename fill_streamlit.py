"""Streamlit UI for filling and submitting Google Forms.

Flow:
1. Enter form URL and load fields.
2. Review detected fields and provide values.
3. Choose submission count.
4. Submit and review success/failure summary.
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

import form


def _field_label(entry: dict[str, Any], index: int) -> str:
    label = f"{index}. {entry['container_name']}"
    if entry.get("name"):
        label += f" - {entry['name']}"
    if entry.get("required"):
        label += " (required)"
    return label


def _render_value_input(entry: dict[str, Any], index: int) -> Any:
    key_base = f"field_{index}_{entry['id']}"
    options = entry.get("options") or []
    required = bool(entry.get("required"))
    field_type = entry.get("type")
    allow_custom_value = form.ANY_TEXT_FIELD in options
    allowed_options = [opt for opt in options if opt != form.ANY_TEXT_FIELD]
    label = _field_label(entry, index)

    if entry.get("default_value") is not None:
        st.caption(f"Auto value used: {entry['default_value']}")
        return entry["default_value"]

    if field_type == 4 and allowed_options:
        selected = st.multiselect(label, options=allowed_options, key=f"{key_base}_multi")
        if required and not selected:
            st.warning(f"Field {index} is required.")
        return selected

    if allowed_options and not allow_custom_value:
        if not required:
            allowed_options = [""] + allowed_options
        return st.selectbox(label, options=allowed_options, key=f"{key_base}_select")

    if allowed_options and allow_custom_value:
        choice = st.selectbox(
            f"{label} (pick option or choose custom)",
            options=["-- custom --"] + allowed_options,
            key=f"{key_base}_choice",
        )
        if choice != "-- custom --":
            return choice

    value = st.text_input(label, key=f"{key_base}_text")
    if required and not value:
        st.warning(f"Field {index} is required.")
    return value


def _build_payload(entries: list[dict[str, Any]], values: list[Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for entry, value in zip(entries, values):
        if entry.get("type") == "required":
            key = entry["id"]
        else:
            key = f"entry.{entry['id']}"
        payload[key] = value
    return payload


def _validate_required(entries: list[dict[str, Any]], values: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, (entry, value) in enumerate(zip(entries, values), start=1):
        if not entry.get("required"):
            continue
        if isinstance(value, list) and not value:
            errors.append(f"Field {index} is required but empty.")
        elif not isinstance(value, list) and value in (None, ""):
            errors.append(f"Field {index} is required but empty.")
    return errors


def main() -> None:
    st.set_page_config(page_title="Google Form Stream Filler", page_icon="📝")
    st.title("Google Form Stream Filler")
    st.write("Load a form, fill each field, then submit multiple times.")

    if "entries" not in st.session_state:
        st.session_state.entries = None
    if "last_url" not in st.session_state:
        st.session_state.last_url = ""

    url = st.text_input("Google Form URL", value=st.session_state.last_url)

    if st.button("Load Form Fields", type="primary"):
        if not url.strip():
            st.error("Please enter a form URL.")
        else:
            entries = form.parse_form_entries(url.strip())
            if not entries:
                st.error("Could not parse form fields from this URL.")
            else:
                st.session_state.entries = entries
                st.session_state.last_url = url.strip()
                st.success(f"Loaded {len(entries)} fields.")

    entries = st.session_state.entries
    if not entries:
        st.info("Load a form URL to continue.")
        return

    st.subheader("Detected Fields")
    values: list[Any] = []
    for i, entry in enumerate(entries, start=1):
        st.markdown(f"**{_field_label(entry, i)}**")
        if entry.get("options"):
            st.caption(f"Options: {entry['options']}")
        values.append(_render_value_input(entry, i))
        st.divider()

    submit_count = st.number_input(
        "How many times should this payload be submitted?",
        min_value=1,
        value=1,
        step=1,
    )

    payload = _build_payload(entries, values)
    st.subheader("Payload Preview")
    st.json(payload)

    if st.button("Submit", type="primary"):
        required_errors = _validate_required(entries, values)
        if required_errors:
            for message in required_errors:
                st.error(message)
            return

        response_url = form.get_form_response_url(st.session_state.last_url)
        success = 0
        failed = 0
        status_lines: list[str] = []

        for attempt in range(1, int(submit_count) + 1):
            try:
                res = requests.post(response_url, data=payload, timeout=10)
                if res.status_code == 200:
                    success += 1
                    status_lines.append(f"[{attempt}/{int(submit_count)}] success")
                else:
                    failed += 1
                    status_lines.append(
                        f"[{attempt}/{int(submit_count)}] failed: status {res.status_code}"
                    )
            except requests.RequestException as exc:
                failed += 1
                status_lines.append(f"[{attempt}/{int(submit_count)}] failed: {exc}")

        st.subheader("Submission Result")
        st.write(f"Success: {success} | Failed: {failed}")
        st.text("\n".join(status_lines))


if __name__ == "__main__":
    main()
