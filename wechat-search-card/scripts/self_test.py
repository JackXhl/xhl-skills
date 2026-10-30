"""Render two cards and check the gates that must not be skipped."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).with_name("render_card.py")
GREEN = (7, 193, 96)


def fake_qr(path: Path) -> None:
    im = Image.new("RGB", (258, 258), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.ellipse([8, 8, 249, 249], fill=(80, 190, 150))
    draw.rounded_rectangle([90, 100, 168, 160], radius=12, fill=(255, 255, 255))
    im.save(path, "PNG")


def run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def green_pixels(path: Path) -> int:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        count = 0
        step = 3
        for y in range(0, rgba.height, step):
            for x in range(0, rgba.width, step):
                r, g, b, a = rgba.getpixel((x, y))
                if a > 200 and abs(r - GREEN[0]) < 8 and abs(g - GREEN[1]) < 8 and abs(b - GREEN[2]) < 8:
                    count += 1
        return count


def rightmost(path: Path, pred) -> int:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        found = -1
        limit = min(680, rgba.height)
        for y in range(420, limit):
            for x in range(rgba.width - 1, 700, -1):
                if pred(rgba.getpixel((x, y))):
                    found = max(found, x)
                    break
        return found


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        qr = root / "code.png"
        fake_qr(qr)

        missing = run("--qr", str(qr), "--keyword", "   ")
        assert missing.returncode == 2, missing.stderr

        gone = run("--qr", str(root / "missing.png"), "--keyword", "山雀")
        assert gone.returncode == 2, gone.stderr

        bad = root / "bad.png"
        bad.write_text("not an image", encoding="utf-8")
        broken = run("--qr", str(bad), "--keyword", "山雀", "--out", str(root / "bad-out.png"))
        assert broken.returncode == 2, broken.stderr

        no_font = run("--qr", str(qr), "--keyword", "山雀", "--font", str(root / "nope.otf"))
        assert no_font.returncode == 2, no_font.stderr

        long = run("--qr", str(qr), "--keyword", "这是一个超过十二个字的搜索词")
        assert long.returncode == 2, long.stderr
        assert "--allow-long" in long.stderr

        blocked = root / "微信搜一搜-山雀视频下载.png"
        blocked.write_bytes(b"no")
        exists = run("--qr", str(qr), "--keyword", "山雀视频下载", "--out", str(blocked))
        assert exists.returncode == 3, exists.stderr

        short = root / "short.png"
        long_out = root / "long.png"
        a = run("--qr", str(qr), "--keyword", "山雀", "--out", str(short))
        b = run("--qr", str(qr), "--keyword", "山雀视频下载", "--out", str(long_out), "--force")
        assert a.returncode == 0, a.stderr
        assert b.returncode == 0, b.stderr

        with Image.open(short) as short_im, Image.open(long_out) as long_im:
            assert short_im.size[1] == 754
            long_width = long_im.size[0]
            assert long_width >= short_im.size[0]
            corner = short_im.convert("RGBA").getpixel((0, 0))
            assert corner[3] == 0
        assert green_pixels(long_out) > green_pixels(short)
        assert b.returncode == 0

        white_x = rightmost(long_out, lambda p: p[3] > 200 and p[0] > 250 and p[1] > 250 and p[2] > 250)
        green_x = rightmost(
            long_out,
            lambda p: p[3] > 200 and abs(p[0] - GREEN[0]) < 12 and abs(p[1] - GREEN[1]) < 12 and abs(p[2] - GREEN[2]) < 12,
        )
        assert 0 < white_x < green_x < long_width - 80

        with Image.open(long_out) as card:
            # Circular code: the square's corner wedge is the card gray, not a white box.
            assert card.convert("RGBA").getpixel((62, 62))[:3] == (247, 247, 247)

        square = root / "square.png"
        sq = Image.new("RGB", (258, 258), (255, 255, 255))
        ImageDraw.Draw(sq).rectangle([16, 16, 100, 100], fill=(0, 0, 0))
        sq.save(square)
        square_out = root / "square-card.png"
        sq_run = run("--qr", str(square), "--keyword", "山雀", "--out", str(square_out))
        assert sq_run.returncode == 0, sq_run.stderr
        with Image.open(square_out) as card:
            pixel = card.convert("RGBA").getpixel((62, 62))
            assert pixel[3] == 255 and pixel[0] > 250

        allowed = run(
            "--qr",
            str(qr),
            "--keyword",
            "山雀视频下载山雀视频下载",
            "--allow-long",
            "--out",
            str(root / "allowed.png"),
        )
        assert allowed.returncode == 0, allowed.stderr

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
