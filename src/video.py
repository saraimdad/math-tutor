from __future__ import annotations

import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

from src.tutor import Tutor


WIDTH, HEIGHT = 1280, 720
WALL = "#dcecf5"
FLOOR = "#c89f72"
BOARD = "#fffef8"
INK = "#243746"
ACCENT = "#1677c8"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _wrapped(text: str, width: int) -> str:
    lines = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    return "\n".join(lines)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    max_size: int,
    bold: bool = False,
) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    """Wrap and shrink text until it fits inside its whiteboard area."""
    for size in range(max_size, 17, -2):
        font = _font(size, bold)
        characters = max(12, int(max_width / (size * 0.58)))
        wrapped = _wrapped(text, characters)
        box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        if box[2] <= max_width and box[3] <= max_height:
            return wrapped, font
    return _wrapped(text, 85), _font(18, bold)


def _frame(scene: dict[str, str], progress: float, scene_number: int, total: int) -> np.ndarray:
    image = Image.new("RGB", (WIDTH, HEIGHT), WALL)
    draw = ImageDraw.Draw(image)

    # Classroom wall, floor, bunting, and whiteboard.
    draw.rectangle((0, 640, WIDTH, HEIGHT), fill=FLOOR)
    colors = ["#ef5b5b", "#f4b942", "#43aa8b", "#577590"]
    for index, x in enumerate(range(20, WIDTH, 80)):
        draw.polygon(((x, 0), (x + 55, 0), (x + 28, 35)), fill=colors[index % len(colors)])
    draw.rounded_rectangle((55, 55, 1225, 650), radius=18, fill="#8a9aa5")
    draw.rounded_rectangle((68, 68, 1212, 622), radius=10, fill=BOARD)
    draw.rectangle((55, 615, 1225, 650), fill="#71808a")
    draw.rounded_rectangle((960, 621, 1050, 640), radius=6, fill="#e9eef2")
    for x, color in ((1080, "#1677c8"), (1125, "#e24a4a"), (1170, "#252525")):
        draw.rounded_rectangle((x, 625, x + 34, 633), radius=4, fill=color)

    draw.text(
        (100, 92),
        f"LESSON {scene_number} / {total}",
        font=_font(24, bold=True),
        fill=ACCENT,
    )
    heading, heading_font = _fit_text(draw, scene["heading"], 1020, 130, 48, bold=True)
    draw.multiline_text(
        (100, 140),
        heading,
        font=heading_font,
        fill=INK,
        spacing=8,
    )

    visual = scene["visual"]
    visible_characters = max(1, round(len(visual) * min(progress * 2.2, 1)))
    visible_visual = visual[:visible_characters]
    fitted_visual, visual_font = _fit_text(draw, visible_visual, 1020, 255, 42)
    draw.line((100, 290, 1180, 290), fill="#b8d4e5", width=3)
    draw.multiline_text(
        (115, 320),
        fitted_visual,
        font=visual_font,
        fill="#174f3f",
        spacing=8,
    )

    draw.rounded_rectangle((100, 585, 1180, 598), radius=7, fill="#d7e0e5")
    draw.rounded_rectangle((100, 585, 100 + int(1080 * progress), 598), radius=7, fill=ACCENT)
    return np.asarray(image)


def create_video(tutor: Tutor, scenes: list[dict[str, str]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clips: list[VideoClip] = []
    audio_clips: list[AudioFileClip] = []

    with TemporaryDirectory() as temp_dir:
        for index, scene in enumerate(scenes, start=1):
            audio_path = Path(temp_dir) / f"scene-{index}.mp3"
            tutor.narrate(scene["narration"], str(audio_path))
            audio = AudioFileClip(str(audio_path))
            audio_clips.append(audio)
            duration = max(audio.duration + 0.4, 2.0)

            clip = VideoClip(
                frame_function=lambda t, s=scene, d=duration, i=index: _frame(
                    s, min(t / d, 1), i, len(scenes)
                ),
                duration=duration,
            ).with_audio(audio)
            clips.append(clip)

        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        final.close()
        for clip in clips:
            clip.close()
        for audio in audio_clips:
            audio.close()

    return output_path
