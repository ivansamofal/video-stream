import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

QUALITIES = [
    {"name": "360p",  "height": 360,  "bitrate": "800k",  "maxrate": "856k",  "bufsize": "1200k", "audio": "96k"},
    {"name": "720p",  "height": 720,  "bitrate": "2800k", "maxrate": "2996k", "bufsize": "4200k", "audio": "128k"},
    {"name": "1080p", "height": 1080, "bitrate": "5000k", "maxrate": "5350k", "bufsize": "7500k", "audio": "192k"},
]


def get_duration(input_path: str) -> int | None:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", input_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    try:
        return int(float(data["format"]["duration"]))
    except (KeyError, ValueError):
        return None


def generate_thumbnail(input_path: str, output_path: str, duration: int | None) -> None:
    seek = 1
    if duration and duration > 10:
        seek = min(30, duration // 10)
    cmd = [
        "ffmpeg", "-y", "-ss", str(seek), "-i", input_path,
        "-frames:v", "1", "-q:v", "3", "-vf", "scale=640:-2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail generation failed: {result.stderr[-1000:]}")


def transcode_to_hls(input_path: str, output_dir: str) -> str:
    """
    Transcode input_path to multi-bitrate HLS inside output_dir.
    Returns path to master.m3u8.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    segment_duration = 6
    master_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

    for q in QUALITIES:
        q_dir = out / q["name"]
        q_dir.mkdir(exist_ok=True)

        cmd = [
            "ffmpeg", "-i", input_path,
            "-vf", f"scale=-2:{q['height']}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-b:v", q["bitrate"], "-maxrate", q["maxrate"], "-bufsize", q["bufsize"],
            "-c:a", "aac", "-b:a", q["audio"], "-ac", "2",
            "-hls_time", str(segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(q_dir / "seg%03d.ts"),
            str(q_dir / "index.m3u8"),
        ]

        logger.info("Transcoding to %s: %s", q["name"], " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed for {q['name']}: {result.stderr[-2000:]}")

        bandwidth = int(q["bitrate"].replace("k", "")) * 1000
        master_lines += [
            f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={"x".join(["0", str(q["height"])])}',
            f'{q["name"]}/index.m3u8',
        ]

    master_path = out / "master.m3u8"
    master_path.write_text("\n".join(master_lines) + "\n")
    return str(master_path)
