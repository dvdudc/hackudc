import os
import json
import glob
import yt_dlp

SUB_PREVIEW = 2_500
MAX_DESC    = 3_000

def get_video_info(url: str) -> str:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "writesubtitles": False,
        "subtitleslangs": ["es", "en"],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_id    = info.get("id", "N/A")
    title       = info.get("title", "N/A")
    channel     = info.get("channel", info.get("uploader", "N/A"))
    description = info.get("description", "").strip() or "Sin descripción"

    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    all_subs  = {**auto_subs, **subtitles}

    sub_text = "Sin subtítulos"
    for lang in ["es", "en"]:
        if lang in all_subs:
            ydl_opts_sub = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [lang],
                "subtitlesformat": "json3",
                "outtmpl": f"/tmp/yt_sub_{video_id}",
            }
            with yt_dlp.YoutubeDL(ydl_opts_sub) as ydl2:
                ydl2.download([url])

            sub_files = glob.glob(f"/tmp/yt_sub_{video_id}.{lang}*.json3")
            if sub_files:
                with open(sub_files[0], encoding="utf-8") as f:
                    data = json.load(f)
                lines = []
                for event in data.get("events", []):
                    for seg in event.get("segs", []):
                        t = seg.get("utf8", "").strip()
                        if t and t != "\n":
                            lines.append(t)
                sub_text = " ".join(lines)
                for sf in sub_files:
                    os.remove(sf)
            break

    if len(sub_text) > SUB_PREVIEW:
        sub_text = sub_text[:SUB_PREVIEW] + "... [continúa]"
    if len(description) > MAX_DESC:
        description = description[:MAX_DESC] + "... [continúa]"

    output = f"""TÍTULO    : {title}
URL       : {url}
ID        : {video_id}
CANAL     : {channel}
DESC      : {description}""".strip()

    return output



print(get_video_info('https://youtu.be/4ypQPJUbYLA?si=dwdbX6-bpIZtSekR'))