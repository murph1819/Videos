# GTA 6 Shorts Maker

Turns gameplay clips into vertical 1080x1920 shorts for YouTube Shorts, TikTok and Reels.

1. Put your raw clips in `Clips/`, **or** just give it a link
   (YouTube, Instagram, TikTok, Twitch, X, ...). Needs `pip install yt-dlp`.
2. Run one of these:

```bash
python3 make_short.py Clips/myclip.mp4                         # auto-picks the loudest 30s
python3 make_short.py Clips/myclip.mp4 --length 45             # loudest 45s
python3 make_short.py Clips/myclip.mp4 --start 1:12 --end 1:40 # exact part
python3 make_short.py Clips/myclip.mp4 --title "NO WAY"        # caption at top
python3 make_short.py Clips/myclip.mp4 --style crop            # zoomed full-screen
python3 make_short.py Clips/                                   # every clip in the folder
python3 make_short.py "https://youtu.be/XXXX" --title "NO WAY" # download + make short
```

3. The result lands in `Finished/<name>_short.mp4`

Videos in `Clips/` and `Finished/` are git-ignored, so they're only pushed when you ask.

Only use clips you own or have permission to repost — reuploading other creators'
footage can get your account copyright strikes.
