#!/usr/bin/env python3
"""Turn a GTA 6 gameplay clip into a vertical short (9:16, 1080x1920).

Usage examples:
  python3 make_short.py Clips/heist.mp4                      # auto-pick the best 30s
  python3 make_short.py Clips/heist.mp4 --length 45          # auto-pick the best 45s
  python3 make_short.py Clips/heist.mp4 --start 1:12 --end 1:40
  python3 make_short.py Clips/heist.mp4 --title "NO WAY THAT WORKED"
  python3 make_short.py Clips/heist.mp4 --style crop         # full-screen center crop
  python3 make_short.py Clips/                               # every clip in the folder
  python3 make_short.py "https://youtube.com/watch?v=..."    # download, then make short
  (works with YouTube, Instagram, TikTok, Twitch, X and more via yt-dlp)

Output goes to Finished/<clip name>_short.mp4. Nothing is uploaded or pushed.
"""
import argparse
import array
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "Clips"
FINISHED = ROOT / "Finished"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
W, H = 1080, 1920


def parse_time(t):
    """Accepts 75, 75.5, 1:15 or 0:01:15."""
    if t is None:
        return None
    secs = 0.0
    for part in str(t).split(":"):
        secs = secs * 60 + float(part)
    return secs


def duration_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def has_audio(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout
    return bool(out.strip())


def loudest_window(path, length, total):
    """Find the start time of the loudest `length`-second stretch.
    Gunfights, crashes and explosions are loud, so this is a decent
    'highlight' guess."""
    rate = 8000
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True, check=True).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - len(raw) % 2])
    # energy per second
    energy = []
    for i in range(0, len(samples), rate):
        chunk = samples[i:i + rate]
        energy.append(sum(s * s for s in chunk[::8]) / max(1, len(chunk[::8])))
    win = int(length)
    if len(energy) <= win:
        return 0.0
    cur = sum(energy[:win])
    best_start, best = 0, cur
    for s in range(1, len(energy) - win + 1):
        cur += energy[s + win - 1] - energy[s - 1]
        if cur > best:
            best, best_start = cur, s
    return float(min(best_start, max(0.0, total - length)))


def title_file(title, out):
    """Write the caption to a text file so any characters (%, :, ') work."""
    f = out.with_suffix(".title.txt")
    f.write_text(title, encoding="utf-8")
    return f


def build_filter(style, title_path, title_len=0):
    if style == "crop":
        chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H},setsar=1[v]")
    else:  # blur: full gameplay in the middle, blurred copy filling the frame
        chain = (f"[0:v]split=2[bg][fg];"
                 f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H},boxblur=20:2,eq=brightness=-0.08[bgb];"
                 f"[fg]scale={W}:-2[fgs];"
                 f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
    if title_path:
        chain = chain[:-3] + (
            f",drawtext=fontfile={FONT}:textfile='{title_path}':expansion=none:"
            f"fontcolor=white:fontsize={max(40, min(78, int(1650 / max(1, title_len))))}:borderw=6:bordercolor=black:"
            f"x=(w-text_w)/2:y=h*0.14[v]")
    return chain


class _QuietLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def download(url):
    """Download a video from YouTube, Instagram, TikTok, etc. into Clips/."""
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp isn't installed. Run:  pip install yt-dlp")
    CLIPS.mkdir(exist_ok=True)
    opts = {
        "outtmpl": str(CLIPS / "%(title).60B [%(id)s].%(ext)s"),
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _QuietLogger(),
        "restrictfilenames": True,
    }
    print(f"> downloading {url}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    except Exception as e:  # network blocked, private video, login needed...
        msg = str(e).splitlines()[0]
        if "403" in msg and "proxy" in msg.lower():
            msg = "this network blocks that site"
        sys.exit(f"  download failed: {msg[:200]}")
    if not path.exists():  # merged file may have a different extension
        found = sorted(CLIPS.glob(f"*[[]{info['id']}[]].*"))
        if not found:
            sys.exit("  download finished but the file wasn't found")
        path = found[0]
    print(f"  saved {path.relative_to(ROOT)}")
    return path


def make_short(src, args):
    total = duration_of(src)
    start = parse_time(args.start)
    end = parse_time(args.end)

    if start is None and end is None:
        length = min(args.length, total)
        start = loudest_window(src, length, total) if has_audio(src) else 0.0
        how = "auto-picked loudest part"
    else:
        start = start or 0.0
        end = end if end is not None else min(total, start + args.length)
        length = end - start
        how = "your times"
    if length <= 0:
        sys.exit(f"{src.name}: end must be after start")
    if length > 60:
        print(f"  note: {length:.0f}s is over 60s; YouTube Shorts allows up to "
              f"3 min but TikTok/Reels play best under 60s")

    FINISHED.mkdir(exist_ok=True)
    out = FINISHED / f"{src.stem}_short.mp4"
    tpath = title_file(args.title, out) if args.title else None
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(src),
           "-filter_complex", build_filter(args.style, tpath, len(args.title or '')),
           "-map", "[v]"]
    if has_audio(src):
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
            str(out)]
    print(f"> {src.name}: {start:.1f}s to {start + length:.1f}s ({how})")
    try:
        subprocess.run(cmd, check=True)
    finally:
        if tpath:
            tpath.unlink(missing_ok=True)
    print(f"  saved {out.relative_to(ROOT)}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="a video file, a folder of clips, or a link "
                        "(YouTube, Instagram, TikTok, ...)")
    p.add_argument("--start", help="start time, e.g. 1:12")
    p.add_argument("--end", help="end time, e.g. 1:40")
    p.add_argument("--length", type=float, default=30,
                   help="seconds to keep when auto-picking (default 30)")
    p.add_argument("--title", help="caption shown at the top")
    p.add_argument("--style", choices=["blur", "crop"], default="blur",
                   help="blur = whole frame on blurred background (default); "
                        "crop = zoomed center crop that fills the screen")
    args = p.parse_args()

    if args.input.startswith(("http://", "https://", "www.")):
        make_short(download(args.input), args)
        return
    src = Path(args.input)
    if src.is_dir():
        clips = sorted(f for f in src.iterdir() if f.suffix.lower() in VIDEO_EXTS)
        if not clips:
            sys.exit(f"no video files in {src}")
        for c in clips:
            make_short(c, args)
    elif src.is_file():
        make_short(src, args)
    else:
        sys.exit(f"not found: {src}")


if __name__ == "__main__":
    main()
