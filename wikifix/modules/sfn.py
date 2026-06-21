"""
Shortened footnote (SFN) converter module.

Converts inline ``<ref>{{cite ...}}</ref>{{Reference page|page=X}}``
and ``<ref name="X" />{{Reference page|page=X}}`` to
``{{sfn|Surname|Year|p=X}}`` templates and collects full
citations in a ``==Sources==`` section.

Named ref reuses (``<ref name="X" />``) whose definition was
converted are also converted to ``{{sfn|Surname|Year}}``.
"""

import re
from collections import OrderedDict

_BODY_CAPTURE = r"([^}]*(?:\{\{[^}]*\}\}[^}]*)*)"

_COMBINED_RE = re.compile(
    r"(?:"
    rf"(<ref[^>]*>)\s*{{{{(cite\s+\w+|citation)\s*{_BODY_CAPTURE}}}}}\s*(</ref>)"
    r"|"
    r'<ref\s+name\s*=\s*"([^"]*)"\s*/>'
    r"|"
    r"<ref\s+name\s*=\s*([^\s\">/]+)\s*/>"
    r")"
    r"\s*\{\{Reference page\s*\|\s*(page|pages|p|pp)\s*=\s*([^}]+)\}\}",
    re.IGNORECASE,
)

_NAMED_REF_DEF_RE = re.compile(
    r'<ref\s+name\s*=\s*"([^"]*)"\s*>\s*\{\{(cite\s+\w+|citation)\s*'
    + _BODY_CAPTURE
    + r"\}\}\s*</ref>",
    re.IGNORECASE,
)
_NAMED_REF_DEF_UNQUOTED_RE = re.compile(
    r"<ref\s+name\s*=\s*([^\s\">/]+)\s*>\s*\{\{(cite\s+\w+|citation)\s*"
    + _BODY_CAPTURE
    + r"\}\}\s*</ref>",
    re.IGNORECASE,
)

_NAMED_REF_REUSE_RE = re.compile(
    r'<ref\s+name\s*=\s*"([^"]*)"\s*/>|<ref\s+name\s*=\s*([^\s\">/]+)\s*/>',
    re.IGNORECASE,
)


def convert_to_sfn(text: str) -> str:
    reflist_end = _reflist_end(text)

    definitions: dict[str, tuple[str, str, dict[str, str]]] = {}
    for m in _NAMED_REF_DEF_RE.finditer(text):
        name = m.group(1)
        definitions[name] = (m.group(2), m.group(3).strip(), _parse_params(m.group(3)))
    for m in _NAMED_REF_DEF_UNQUOTED_RE.finditer(text):
        name = m.group(1)
        if name not in definitions:
            definitions[name] = (
                m.group(2),
                m.group(3).strip(),
                _parse_params(m.group(3)),
            )

    replacements: list[tuple[int, int, str]] = []
    seen: OrderedDict[str, str] = OrderedDict()
    converted_names: set[str] = set()

    for m in _COMBINED_RE.finditer(text):
        if reflist_end is not None and m.end() > reflist_end:
            continue

        page_key = m.group(7)
        page_val = m.group(8).strip()
        authors: list[str] = []
        year: str | None = None
        full_bib: str | None = None

        if m.group(1) is not None:
            open_ref = m.group(1)
            template = m.group(2)
            body = m.group(3).strip()

            name_m = re.search(
                r'name\s*=\s*"([^"]*)"|name\s*=\s*([^\s>/]+)', open_ref, re.IGNORECASE
            )
            ref_name = name_m.group(1) or name_m.group(2) if name_m else None
            if ref_name:
                converted_names.add(ref_name)

            params = _parse_params(body)
            authors = _get_authors(params)
            if not authors:
                continue
            year = _get_year(params)
            if not year:
                continue
            full_bib = _format_source(template, body)
        else:
            name = m.group(5) or m.group(6)
            if not name or name not in definitions:
                continue
            converted_names.add(name)

            template, body, params = definitions[name]
            authors = _get_authors(params)
            if not authors:
                continue
            year = _get_year(params)
            if not year:
                continue
            full_bib = _format_source(template, body)

        sfn = _build_sfn(authors, year, page_val, page_key)
        if full_bib:
            hash_key = f"{'|'.join(authors)}|{year}"
            if hash_key not in seen:
                seen[hash_key] = full_bib

        replacements.append((m.start(), m.end(), sfn))

    for start, end, sfn in reversed(replacements):
        text = text[:start] + sfn + text[end:]

    # Convert named ref reuses whose definition was converted
    reuse_replacements: list[tuple[int, int, str]] = []
    for m in _NAMED_REF_REUSE_RE.finditer(text):
        name = m.group(1) or m.group(2)
        if name and name in converted_names and name in definitions:
            template, body, params = definitions[name]
            authors = _get_authors(params)
            if not authors:
                continue
            year = _get_year(params)
            if not year:
                continue
            sfn = _build_sfn(authors, year, None, "page")
            reuse_replacements.append((m.start(), m.end(), sfn))

    for start, end, sfn in reversed(reuse_replacements):
        text = text[:start] + sfn + text[end:]

    # Convert duplicates (same author+year still in ref tags)
    if seen:
        converted_keys = set(seen.keys())
        dup_ref_re = re.compile(
            r"<ref[^>]*>\s*\{\{(?:cite\s+\w+|citation)\s*"
            + _BODY_CAPTURE
            + r"\}\}\s*</ref>",
            re.IGNORECASE,
        )
        dup_replacements: list[tuple[int, int, str]] = []
        for dm in dup_ref_re.finditer(text):
            if reflist_end is not None and dm.start() > reflist_end:
                continue
            body = dm.group(1).strip()
            params = _parse_params(body)
            dup_authors = _get_authors(params)
            if not dup_authors:
                continue
            dup_year = _get_year(params)
            if not dup_year:
                continue
            dup_key = f"{'|'.join(dup_authors)}|{dup_year}"
            if dup_key in converted_keys:
                dup_sfn = _build_sfn(dup_authors, dup_year, None, "page")
                dup_replacements.append((dm.start(), dm.end(), dup_sfn))

        for start, end, dup_sfn in reversed(dup_replacements):
            text = text[:start] + dup_sfn + text[end:]

    # Append/merge sources section
    if seen:
        sources_heading_re = re.compile(r"^==\s*Sources\s*==", re.MULTILINE)
        existing_sources = sources_heading_re.search(text)
        if existing_sources:
            sources_start = existing_sources.end()
            next_section = re.compile(r"^==\s*\w", re.MULTILINE)
            next_m = next_section.search(text, sources_start)
            sources_end = next_m.start() if next_m else len(text)
            existing_bullets = re.findall(
                r"^\* .+", text[sources_start:sources_end], re.MULTILINE
            )
            existing_set = set(existing_bullets)
            new_lines = []
            for full_bib in seen.values():
                bullet = f"* {full_bib}"
                if bullet not in existing_set:
                    new_lines.append(bullet)
            if new_lines:
                prefix = text[:sources_end].rstrip("\n") + "\n"
                text = prefix + "\n".join(new_lines) + "\n" + text[sources_end:]
        else:
            reflist_heading = re.compile(
                r"^==\s*(?:References|Notes|Footnotes)\s*==", re.MULTILINE
            )
            reflist_m = reflist_heading.search(text)
            src_lines = ["==Sources=="] + [f"* {s}" for s in seen.values()] + [""]
            src_block = "\n" + "\n".join(src_lines) + "\n"
            if reflist_m:
                text = text[: reflist_m.start()] + src_block + text[reflist_m.start() :]
            else:
                text += src_block

    return text


def _reflist_end(text: str) -> int | None:
    for heading in (
        r"==\s*References\s*==",
        r"==\s*Notes\s*==",
        r"==\s*Footnotes\s*==",
        r"==\s*Sources\s*==",
    ):
        m = re.search(heading, text)
        if m:
            return m.start()
    return None


def _parse_params(body: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for m in re.finditer(r"\|\s*([\w-]+)\s*=\s*([^|}]+)", body):
        params[m.group(1).strip().lower()] = m.group(2).strip()
    return params


def _get_authors(params: dict[str, str]) -> list[str]:
    authors: list[str] = []
    for i in range(1, 13):
        key = "last1" if i == 1 else f"last{i}"
        if key in params:
            authors.append(params[key].rstrip(","))
        elif i == 1 and "last" in params:
            authors.append(params["last"].rstrip(","))
        else:
            break
        if len(authors) >= 4:
            break
    if not authors and "vauthors" in params:
        parts = params["vauthors"].split(",")
        for part in parts:
            name = part.strip().split()
            if name and name[0].lower() not in ("et", "etal"):
                authors.append(name[0].rstrip(","))
            if len(authors) >= 4:
                break
    return authors


def _get_year(params: dict[str, str]) -> str | None:
    for key in ("year", "date"):
        if key in params:
            m = re.search(r"(\d{4})", params[key])
            if m:
                return m.group(1)
    return None


def _build_sfn(
    authors: list[str], year: str, page_val: str | None, page_key: str = "page"
) -> str:
    parts = ["sfn"] + [a.replace("|", "{{!}}") for a in authors[:4]]
    parts.append(year)
    if page_val:
        prefix = "pp" if page_key in ("pages", "pp") else "p"
        parts.append(f"{prefix}={page_val}")
        if len(authors) > 4:
            parts[-1] += "|ref=none"
    elif len(authors) > 4:
        parts.append("ref=none")
    return "{{" + "|".join(parts) + "}}"


def _format_source(template: str, body: str) -> str:
    clean = body.strip().lstrip("|").strip()
    return f"{{{{{template} |{clean}}}}}"
