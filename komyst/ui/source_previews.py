"""Public home-page previews, refreshed on demand with an isolated browser."""

import base64
import io
import os
import re
import threading
import time

SUPPORTED_SOURCE_URLS = {
    "webtoon": "https://www.webtoons.com/en/",
    "comix": "https://comix.to/browse?genres_in=101137",
    "vortex": "https://vortexscans.org/",
    "naver": "https://comic.naver.com/webtoon",
    "mangadex": "https://mangadex.org/",
    "tapas": "https://tapas.io/",
    "inkr": "https://comics.inkr.com/",
}
REFRESH_SECONDS = 60
# defer: a handful of public sources per local server, use a shared cache if hosting multiple servers.
_cache = {}
_cache_lock = threading.Lock()
_browser_lock = threading.Lock()


def _capture(key):
    from PIL import Image
    from selenium.webdriver.support.ui import WebDriverWait
    from komyst.download.down import (
        _create_driver, _set_browser_timeouts, _capture_driver_ownership,
        _bounded_driver_teardown,
    )

    # Never attach to the operator's browser or reuse authenticated source profiles.
    with _browser_lock:
        driver = _create_driver()
        ownership = _capture_driver_ownership(driver)
        try:
            _set_browser_timeouts(driver, 20)
            driver.set_window_size(1280, 800)
            driver.get(SUPPORTED_SOURCE_URLS[key])
            WebDriverWait(driver, 10).until(lambda d: d.execute_script(
                "return document.readyState === 'complete' && "
                "Array.from(document.images).some(i => i.complete && i.naturalWidth > 100)"
            ))
            # A browser check that solves itself (a proof-of-work page) is waited out; one
            # that still stands after the wait is reported, never captured as the preview.
            def challenged():
                text = " ".join((driver.title or "", driver.execute_script(
                    "return (document.body && document.body.innerText || '').slice(0, 400)") or "")).lower()
                return any(word in text for word in (
                    "just a moment", "verify you are human", "access denied",
                    "browser verification", "not a bot",
                ))

            deadline = time.monotonic() + 20
            while challenged() and time.monotonic() < deadline:
                time.sleep(1)
            if challenged():
                raise RuntimeError("source_preview_unavailable")
            time.sleep(1.5)  # let the landing page paint its images after the check
            image = Image.open(io.BytesIO(driver.get_screenshot_as_png())).convert("RGB")
            image.thumbnail((800, 500))
            output = io.BytesIO()
            image.save(output, "JPEG", quality=80)
            return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
        finally:
            _bounded_driver_teardown(driver, ownership, timeout_seconds=3, cleanup_timeout_seconds=2)


_featured_index = {"mangadex": 0}


def _preview_font(size, bold=False):
    from pathlib import Path

    from PIL import ImageFont

    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    bundled = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    for candidate in ((windows / ("segoeuib.ttf" if bold else "segoeui.ttf")),
                      (bundled / ("comicneue-bold.ttf" if bold else "comicneue-regular.ttf"))):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _wrap(draw, text, font, width, max_lines):
    lines, current = [], ""
    for word in str(text or "").split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and lines:
        lines[-1] = lines[-1].rstrip(".,;") + "..."
    return [line for line in lines if line]


def _mangadex_featured():
    """MangaDex's landing page sits behind a bot check an automated browser must not pass.
    Its public API gives the same "Popular New Titles": each refresh shows the next one
    (cover, title, genres and synopsis), so the card cycles through them like the site."""
    import datetime

    import requests
    from PIL import Image, ImageDraw, ImageFilter

    from komyst.download.sources.chapter_source import MANGADEX, MANGADEX_API, MANGADEX_USER_AGENT

    headers = {"User-Agent": MANGADEX_USER_AGENT}
    query = f"{MANGADEX_API}/manga"
    MANGADEX.validate_url(query)
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    response = requests.get(query, headers=headers, timeout=20, params={
        "limit": 10, "includes[]": "cover_art", "order[followedCount]": "desc",
        "contentRating[]": "safe", "hasAvailableChapters": "true", "createdAtSince": since})
    response.raise_for_status()
    titles = [m for m in response.json().get("data") or []
              if any(r.get("type") == "cover_art" for r in m.get("relationships") or ())]
    if not titles:
        raise RuntimeError("source_preview_unavailable")
    index = _featured_index["mangadex"] % len(titles)
    _featured_index["mangadex"] = index + 1
    manga = titles[index]
    attributes = manga.get("attributes") or {}
    art = next(r for r in manga["relationships"] if r.get("type") == "cover_art")
    url = f"https://uploads.mangadex.org/covers/{manga['id']}/{art['attributes']['fileName']}.512.jpg"
    MANGADEX.validate_url(url)
    image = requests.get(url, headers=headers, timeout=20)
    image.raise_for_status()
    cover = Image.open(io.BytesIO(image.content)).convert("RGB")

    width, height = 800, 450
    scale = max(width / cover.width, height / cover.height)
    backdrop = cover.resize((int(cover.width * scale) + 1, int(cover.height * scale) + 1))
    backdrop = backdrop.crop((0, 0, width, height)).filter(ImageFilter.GaussianBlur(6))
    canvas = Image.blend(backdrop, Image.new("RGB", (width, height), (16, 16, 20)), 0.62)
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 22), "MangaDex · Popular New Titles", font=_preview_font(24, True), fill=(255, 255, 255))
    thumb_h = 330
    thumb = cover.resize((int(cover.width * thumb_h / cover.height), thumb_h))
    max_thumb_w = int(thumb_h * 0.72)  # a landscape cover is cropped to a portrait slot
    if thumb.width > max_thumb_w:
        offset = (thumb.width - max_thumb_w) // 2
        thumb = thumb.crop((offset, 0, offset + max_thumb_w, thumb_h))
    canvas.paste(thumb, (28, 84))
    left = 28 + thumb.width + 26
    text_w = width - left - 28
    title_map = attributes.get("title") or {}
    title = title_map.get("en") or next(iter(title_map.values()), "")
    y = 84
    for line in _wrap(draw, title, _preview_font(26, True), text_w, 2):
        draw.text((left, y), line, font=_preview_font(26, True), fill=(255, 255, 255))
        y += 34
    tags = [((t.get("attributes") or {}).get("name") or {}).get("en", "")
            for t in attributes.get("tags") or ()
            if (t.get("attributes") or {}).get("group") == "genre"][:3]
    x, y = left, y + 8
    tag_font = _preview_font(14, True)
    for tag in filter(None, tags):
        tag_w = int(draw.textlength(tag.upper(), font=tag_font)) + 14
        if x + tag_w > width - 28:
            break
        draw.rounded_rectangle((x, y, x + tag_w, y + 22), radius=4, fill=(48, 48, 54))
        draw.text((x + 7, y + 2), tag.upper(), font=tag_font, fill=(235, 235, 235))
        x += tag_w + 8
    y += 38
    description = (attributes.get("description") or {}).get("en", "")
    description = re.sub(r"\[[^\]]*\]\([^)]*\)|[*_#>]|---.*$", "", description, flags=re.S).strip()
    for line in _wrap(draw, description, _preview_font(17), text_w, 8):
        draw.text((left, y), line, font=_preview_font(17), fill=(220, 220, 225))
        y += 24
    output = io.BytesIO()
    canvas.save(output, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


_PREVIEW_BUILDERS = {"mangadex": _mangadex_featured}


def _refresh(key):
    try:
        preview = _PREVIEW_BUILDERS[key]() if key in _PREVIEW_BUILDERS else _capture(key)
        with _cache_lock:
            _cache[key].update(image=preview, captured_at=time.time(), error=False)
    except Exception:
        # A failed refresh keeps the last good preview and its original timestamp.
        with _cache_lock:
            _cache[key]["error"] = True
    finally:
        with _cache_lock:
            _cache[key].update(refreshing=False, checked_at=time.monotonic())


def source_preview(key):
    if key not in SUPPORTED_SOURCE_URLS:
        raise ValueError("unsupported_source")
    with _cache_lock:
        entry = _cache.setdefault(key, {
            "image": "", "captured_at": None, "checked_at": None,
            "refreshing": False, "error": False,
        })
        if not entry["refreshing"] and (
            entry["checked_at"] is None or time.monotonic() - entry["checked_at"] >= REFRESH_SECONDS
        ):
            entry["refreshing"] = True
            threading.Thread(target=_refresh, args=(key,), daemon=True,
                             name=f"source-preview-{key}").start()
        return {field: entry[field] for field in ("image", "captured_at", "refreshing", "error")}
