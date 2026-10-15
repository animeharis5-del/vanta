"""Rich Message UI untuk ZHEE Checker.

Builder: h2, para, info_table, data_table, fold (blok lipat),
checklist (SELALU checked -> centang biru), highlight (sorotan),
footnote (catatan kaki), plus konverter fallback rich_ke_html() ke
HTML standar Telegram.

Transport mentah via httpx:
- kirim_rich()  -> POST sendRichMessage {rich_message:{html}}
- edit_rich()   -> POST editMessageText {rich_message:{html}} (terbukti bisa)
Keduanya return True bila rich terkirim, False bila pemanggil harus
pakai fallback Bot API standar. deteksi_rich() dipanggil sekali saat
start (post_init): 404 -> RICH_MATI = True (hemat request).

Tag <tg-emoji> DIPERTAHANKAN di builder maupun fallback (valid di
parse_mode HTML standar).
"""

import logging
import re

import httpx

logger = logging.getLogger("zhee.rich")

RICH_MATI = False  # True = method tak tersedia -> jangan coba lagi


def _san(value):
    # Amankan "&" mentah tanpa merusak entity/tag yang sudah valid.
    return re.sub(
        r"&(?!(?:amp|lt|gt|quot|apos|#39|#\d+|#x[0-9a-fA-F]+);)",
        "&amp;", str(value if value is not None else ""),
    ).strip()


# ── Builder ────────────────────────────────────────────────────

def rich_h2(title):
    return f"<h2>{_san(title)}</h2>"


def rich_para(text):
    return f"<p>{_san(text)}</p>"


def rich_info_table(rows):
    """Tabel info label : nilai. Label & nilai boleh mengandung tag inline
    (b, i, code, tg-emoji) — tidak di-escape, hanya sanitasi entity."""
    body = "".join(
        f"<tr><td>{_san(r[0])}</td><td>{_san(r[1])}</td></tr>"
        for r in (rows or []) if r and len(r) >= 2
    )
    return f"<table bordered striped>{body}</table>" if body else ""


def rich_data_table(columns, rows, empty_text="Belum ada data"):
    cols = "".join(f"<th>{_html_escape(c)}</th>" for c in (columns or []))
    if rows:
        body = "".join(
            "<tr>" + "".join(f"<td>{_san(c)}</td>" for c in r) + "</tr>"
            for r in rows
        )
    else:
        body = f"<tr><td>{_html_escape(empty_text)}</td></tr>"
    return (f"<table bordered striped><thead><tr>{cols}</tr></thead>"
            f"<tbody>{body}</tbody></table>")


def _html_escape(value):
    import html as _h
    return _h.escape(str(value if value is not None else ""), quote=True)


def rich_fold(title, content, open=False):
    return (f"<details{' open' if open else ''}>"
            f"<summary>{_html_escape(title)}</summary>"
            f"{content or ''}</details>")


def rich_checklist(items):
    """Daftar periksa — SELALU checked (centang biru) sesuai permintaan."""
    rows = []
    for it in (items or []):
        text = it if isinstance(it, str) else (it.get("text") if it else None)
        if not text:
            continue
        rows.append(f'<li><input type="checkbox" checked>{_san(text)}</li>')
    return f"<ul>{''.join(rows)}</ul>" if rows else ""


def rich_highlight(content):
    return f"<mark>{_san(content)}</mark>"


def rich_footnote(name, content, label="1"):
    return (f"<footer><tg-reference name=\"{_html_escape(name)}\">"
            f"{_html_escape(label)}. {_san(content)}"
            f"</tg-reference></footer>")


# ── Konverter fallback: Rich HTML -> HTML standar Telegram ───────

def rich_ke_html(fragment):
    out = str(fragment or "").strip()
    out = _san(out)
    out = re.sub(r"<h[1-6][^>]*>", "<b>", out, flags=re.I)
    out = re.sub(r"</h[1-6]>", "</b>\n", out, flags=re.I)
    out = re.sub(r"<p[^>]*>", "", out, flags=re.I)
    out = re.sub(r"</p>", "\n", out, flags=re.I)
    out = re.sub(r"<br\s*/?>", "\n", out, flags=re.I)
    out = re.sub(r"<details[^>]*>", "\n<blockquote>", out, flags=re.I)
    out = re.sub(r"</details>", "</blockquote>\n", out, flags=re.I)
    out = re.sub(r"<summary[^>]*>", "<b>", out, flags=re.I)
    out = re.sub(r"</summary>", "</b>\n", out, flags=re.I)
    def _mark_repl(m):
        # Hindari <b> bersarang (<b><b>) yang ditolak Telegram
        # dengan Entity_text_invalid: kupas <b> di dalam <mark>.
        inner = re.sub(r"</?b>", "", m.group(1), flags=re.I)
        return f"<b>{inner}</b>"
    out = re.sub(r"<mark[^>]*>(.*?)</mark>", _mark_repl, out,
                 flags=re.I | re.S)
    out = re.sub(r"<footer[^>]*>", "\n", out, flags=re.I)
    out = re.sub(r"</footer>", "", out, flags=re.I)
    out = re.sub(r"<tg-reference\b[^>]*>", "", out, flags=re.I)
    out = re.sub(r"</tg-reference>", "", out, flags=re.I)
    out = re.sub(r"<input[^>]*>", "✅ ", out, flags=re.I)
    out = re.sub(r"<ul[^>]*>", "", out, flags=re.I)
    out = re.sub(r"</ul>", "", out, flags=re.I)
    out = re.sub(r"<li[^>]*>", "• ", out, flags=re.I)
    out = re.sub(r"</li>", "\n", out, flags=re.I)
    out = re.sub(r"<thead[^>]*>|</thead>|<tbody[^>]*>|</tbody>", "", out, flags=re.I)
    out = re.sub(r"<table[^>]*>", "\n<blockquote>", out, flags=re.I)
    out = re.sub(r"</table>", "</blockquote>\n", out, flags=re.I)
    out = re.sub(r"<tr[^>]*>", "", out, flags=re.I)
    out = re.sub(r"</tr>", "\n", out, flags=re.I)
    out = re.sub(r"<th[^>]*>", "<b>", out, flags=re.I)
    out = re.sub(r"</th>", "</b>  ", out, flags=re.I)
    out = re.sub(r"<td[^>]*>", "", out, flags=re.I)
    out = re.sub(r"</td>", " : ", out, flags=re.I)
    # HTML fallback Bot API standar tidak selalu menerima custom emoji dari
    # semua klien/ID pack. Pertahankan emoji fallback-nya, buang tag-nya agar
    # caption /start tidak gagal dengan BadRequest: Entity_text_invalid.
    out = re.sub(r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", r"\1", out,
                 flags=re.I | re.S)
    # Buang tag non-standar yang tersisa.
    out = re.sub(r"</?(?!b|i|u|s|code|pre|a|blockquote)\b[^>]*>",
                 "", out, flags=re.I)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n[ \t]+", "\n", out)
    out = re.sub(r"(?:\s*:\s*){2,}", " : ", out)
    out = re.sub(r" :(\n|$)", r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out or "-"


def ada_tag_rich(s):
    return bool(re.search(r"<(table|details|mark|footer|input|h2)\b",
                          str(s or ""), re.I))


# ── Transport mentah ───────────────────────────────────────────

_API = "https://api.telegram.org/bot{token}/{method}"


async def deteksi_rich(token):
    """Deteksi sekali saat start. chat_id=0 tak pernah valid:
    404 = method tak ada -> RICH_MATI, selain itu anggap ada."""
    global RICH_MATI
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                _API.format(token=token, method="sendRichMessage"),
                json={"chat_id": 0, "rich_message": {"html": "<p>ping</p>"}},
            )
        if r.status_code == 404:
            RICH_MATI = True
            logger.info("Rich Message tak tersedia (404) -> pakai HTML standar.")
        else:
            logger.info("Rich Message tersedia (status %s).", r.status_code)
    except Exception as e:
        logger.info("Rich Message tak dapat dites (%s) -> coba saat dipakai.", e)


async def kirim_rich(token, chat_id, rich_html, keyboard_rich=None):
    """Kirim via sendRichMessage. Return True bila terkirim."""
    global RICH_MATI
    if RICH_MATI or not ada_tag_rich(rich_html):
        return False
    payload = {"chat_id": chat_id, "rich_message": {"html": rich_html}}
    if keyboard_rich:
        payload["reply_markup"] = {"inline_keyboard": keyboard_rich}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(_API.format(token=token, method="sendRichMessage"),
                             json=payload)
        data = r.json() if r.headers.get("content-type", "").startswith(
            "application/json") else {}
        if r.status_code == 404:
            RICH_MATI = True
            return False
        return bool(data.get("ok"))
    except Exception as e:
        logger.debug("kirim_rich gagal: %s", e)
        return False


async def edit_rich(token, chat_id, message_id, rich_html, keyboard_rich=None):
    """Edit via editMessageText + rich_message. Return True bila berhasil."""
    global RICH_MATI
    if RICH_MATI or not ada_tag_rich(rich_html):
        return False
    payload = {"chat_id": chat_id, "message_id": message_id,
               "rich_message": {"html": rich_html}}
    if keyboard_rich:
        payload["reply_markup"] = {"inline_keyboard": keyboard_rich}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(_API.format(token=token, method="editMessageText"),
                             json=payload)
        data = r.json() if r.headers.get("content-type", "").startswith(
            "application/json") else {}
        if r.status_code == 404:
            RICH_MATI = True
            return False
        return bool(data.get("ok"))
    except Exception as e:
        logger.debug("edit_rich gagal: %s", e)
        return False
