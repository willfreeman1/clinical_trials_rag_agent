"""Capture a looping GIF of the laptop demo for the README.

Playwright, not a screen recording: hold times are fixed, there is no
cursor, and one eligibility rule can be cropped tight enough to read.

The demo must already be running (docker compose up, or
python -m service.app on port 8088). This script does not start a GPU
or call a paid model.

Patient 8 (infant, Hirschsprung disease) and trial NCT02216994: four
rules, a short quote from the note, and a rule the note does not settle.
No offered quote was rejected on this pair; frame 5 is "not enough
information", not a staged guardrail failure.

  python scripts/capture_demo_gif.py

The system does not say a patient qualifies.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "demo.gif"
PAPER = (250, 250, 249)
WIDTH = 1000
HEIGHT = 650
ELEMENT_PAD = 28
PATIENT_ID = "8"
NCT_ID = "NCT02216994"
QUOTE_RULE = "Age are from newborn to 3 years old"
NEI_RULE = "Hard or firm stools for 2 or less per week"

# Hold times in milliseconds, in frame order.
HOLDS = {
    "page": 2000,
    "ranked": 2500,
    "expanded": 3000,
    "quote": 3000,
    "nei": 2500,
    "disclaimer": 1500,
}


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def require_demo(url: str) -> None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=3) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        die(
            "The demo is not reachable at "
            f"{url}. Start it first:\n"
            "  docker compose up --build\n"
            "or, without Docker:\n"
            "  set PYTHONPATH to the repo root, PORT=8088, MODEL_MODE=replay\n"
            "  python -m service.app\n"
            f"({exc})"
        )
    if "replay" not in body and "live" not in body:
        die(f"unexpected /health body: {body[:200]}")


def fill(im: Image.Image, width: int, height: int) -> Image.Image:
    """Scale so the crop covers the canvas. No letterbox."""
    im = im.convert("RGB")
    scale = max(width / im.width, height / im.height)
    new_w = max(1, round(im.width * scale))
    new_h = max(1, round(im.height * scale))
    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - width) // 2)
    top = max(0, (new_h - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def assemble(frames: list[tuple[bytes, int]], dest: Path) -> None:
    images: list[Image.Image] = []
    durations: list[int] = []
    for raw, hold in frames:
        im = Image.open(io.BytesIO(raw))
        images.append(fill(im, WIDTH, HEIGHT).quantize(colors=64, method=Image.Quantize.MEDIANCUT))
        durations.append(hold)
    dest.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        dest,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )


async def viewport_png(page) -> bytes:
    return await page.screenshot(type="png", scale="css")


async def scroll_to_top(loc, gap: int = 16) -> None:
    await loc.evaluate(
        """(el, gap) => {
            const y = el.getBoundingClientRect().top + window.scrollY - gap;
            window.scrollTo(0, Math.max(0, y));
        }""",
        gap,
    )


def _grow_to_aspect(x: float, y: float, w: float, h: float, aspect: float) -> tuple[float, float, float, float]:
    if w / h > aspect:
        new_h = w / aspect
        y -= (new_h - h) / 2
        h = new_h
    else:
        new_w = h * aspect
        x -= (new_w - w) / 2
        w = new_w
    return x, y, w, h


async def element_png(page, text: str) -> bytes:
    loc = page.locator("article.rule").filter(has_text=text)
    await loc.first.scroll_into_view_if_needed()
    box = await loc.first.bounding_box()
    if not box:
        raise RuntimeError(f"no box for rule: {text}")
    x = box["x"] - ELEMENT_PAD
    y = box["y"] - ELEMENT_PAD
    w = box["width"] + 2 * ELEMENT_PAD
    h = box["height"] + 2 * ELEMENT_PAD
    x, y, w, h = _grow_to_aspect(x, y, w, h, WIDTH / HEIGHT)
    vw, vh = WIDTH, HEIGHT
    x = max(0, x)
    y = max(0, y)
    if x + w > vw:
        x = max(0, vw - w)
        w = min(w, vw)
    if y + h > vh:
        y = max(0, vh - h)
        h = min(h, vh)
    return await page.screenshot(
        type="png",
        scale="css",
        clip={"x": x, "y": y, "width": w, "height": h},
    )


async def capture(url: str) -> list[tuple[bytes, int]]:
    frames: list[tuple[bytes, int]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        release = asyncio.Event()

        async def hold_match(route):
            await release.wait()
            await route.continue_()

        await page.route("**/v1/match", hold_match)
        await page.goto(url.rstrip("/") + "/", wait_until="networkidle")
        await page.locator("#patients button").first.wait_for()

        await page.locator(f'#patients button[data-id="{PATIENT_ID}"]').click()
        await page.locator("#note").wait_for(state="visible")
        await scroll_to_top(page.locator(f'#patients button[data-id="{PATIENT_ID}"]'))
        frames.append((await viewport_png(page), HOLDS["page"]))

        release.set()
        await page.locator("#results button.row").first.wait_for()
        await page.locator("#mode").filter(has_text="replay").wait_for()
        ranked = page.locator("h2").filter(has_text="Ranked trials")
        await scroll_to_top(ranked)
        frames.append((await viewport_png(page), HOLDS["ranked"]))

        row = page.locator("#results button.row").filter(has_text=NCT_ID)
        await row.click()
        await page.locator("article.rule").first.wait_for()
        await scroll_to_top(ranked)
        frames.append((await viewport_png(page), HOLDS["expanded"]))

        frames.append((await element_png(page, QUOTE_RULE), HOLDS["quote"]))
        frames.append((await element_png(page, NEI_RULE), HOLDS["nei"]))

        await scroll_to_top(page.locator("#disclaimer"))
        frames.append((await viewport_png(page), HOLDS["disclaimer"]))
        await browser.close()
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8088")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    require_demo(args.url)
    frames = asyncio.run(capture(args.url))
    dest = Path(args.out)
    assemble(frames, dest)
    size = dest.stat().st_size
    print(
        f"wrote {dest} {size} bytes {WIDTH}x{HEIGHT} "
        f"patient={PATIENT_ID} trial={NCT_ID} frames={len(frames)}"
    )
    if size > 3 * 1024 * 1024:
        die(f"GIF is {size} bytes; over 3 MB. Drop a frame or reduce the palette.")


if __name__ == "__main__":
    main()
