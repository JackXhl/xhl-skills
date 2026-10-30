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


def run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        qr = root / "code.png"
        fake_qr(qr)

        missing = run("--qr", str(qr), "--keyword", "   ")
        assert missing.returncode == 2, missing.stderr

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
            assert long_im.size[0] >= short_im.size[0]
            corner = short_im.convert("RGBA").getpixel((0, 0))
            assert corner[3] == 0
        assert green_pixels(long_out) > green_pixels(short)
        assert b.returncode == 0

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
