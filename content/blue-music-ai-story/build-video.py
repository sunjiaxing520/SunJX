"""Render a source-labelled documentary edit; never reads business credentials."""
import asyncio
import json
import math
import os
from pathlib import Path
import re
import subprocess
import wave

import edge_tts
import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).parent
STORY = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
OUT = Path(STORY["output"])
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run(args):
    result = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:])


def stamp(seconds, ass=False):
    total = round(seconds * (100 if ass else 1000))
    unit = 100 if ass else 1000
    h, rest = divmod(total, unit * 3600)
    m, rest = divmod(rest, unit * 60)
    s, frac = divmod(rest, unit)
    return f"{h}:{m:02}:{s:02}.{frac:02}" if ass else f"{h:02}:{m:02}:{s:02},{frac:03}"


def captions(text):
    parts = re.split(r"[，。？！：]", text)
    return [p[i:i+18] for p in parts if p for i in range(0, len(p), 18)]


async def main():
    (OUT / "audio").mkdir(parents=True, exist_ok=True)
    lengths = []
    for i, scene in enumerate(STORY["scenes"]):
        mp3 = OUT / "audio" / f"{i:02}.mp3"
        if not mp3.exists() or mp3.stat().st_size < 100:
            print(f"Synthesizing narration {i+1}/9", flush=True)
            for attempt in range(3):
                try:
                    temp = mp3.with_suffix('.part')
                    await edge_tts.Communicate(scene["voice"], STORY["voice"], rate="+0%",
                                               proxy=os.getenv("VIDEO_TTS_PROXY"),
                                               connect_timeout=15, receive_timeout=30).save(str(temp))
                    temp.replace(mp3)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2+attempt*2)
        wav = mp3.with_suffix(".wav")
        run(["-i", mp3, "-ar", "48000", "-ac", "1", wav])
        with wave.open(str(wav)) as audio:
            lengths.append(audio.getnframes()/audio.getframerate())
    total = sum(lengths)
    speed = total / 58.5
    if not 0.75 < speed < 1.35:
        raise RuntimeError(f"Narration requires unnatural speed {speed:.2f}; revise copy instead")
    timings = []
    narration_pcm = []
    start = 0.0
    for i, (scene, length) in enumerate(zip(STORY["scenes"], lengths)):
        duration = round((length/speed + 1.5/9)*30)/30
        if i == 8:
            duration = 60 - start
        timings.append((start, duration))
        processed = OUT/"audio"/f"{i:02}-timed.wav"
        run(["-i", OUT/"audio"/f"{i:02}.wav", "-af", f"atempo={speed:.8f},apad",
             "-t", f"{duration:.8f}", "-ar", "48000", "-ac", "1", processed])
        with wave.open(str(processed)) as audio:
            pcm = audio.readframes(audio.getnframes())
            exact_bytes = round(duration*48000)*2
            narration_pcm.append((pcm+b'\0'*exact_bytes)[:exact_bytes])
        # A subtle push-in uses real stills, not fabricated UI interactions.
        zoom = "zoompan=z='min(zoom+0.00007,1.018)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30"
        run(["-loop", "1", "-framerate", "30", "-i", OUT/"frames"/f"{i:02}.png",
             "-vf", zoom, "-t", f"{duration:.6f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-threads", "2", "-an",
             OUT/f"scene-{i:02}.mp4"])
        start += duration
        print(f"Rendered scene {i+1}/9", flush=True)
    with wave.open(str(OUT/"narration.wav"), "wb") as audio:
        audio.setparams((1,2,48000,0,"NONE","not compressed"))
        audio.writeframes(b''.join(narration_pcm))
    concat = OUT / "concat.txt"
    concat.write_text("\n".join(f"file 'scene-{i:02}.mp4'" for i in range(9)), encoding="utf-8")
    run(["-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", OUT/"assembled.mp4"])
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920",
           "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Default,Microsoft YaHei,44,&H00FFFFFF,&H00FFFFFF,&H00111315,&H00111315,1,0,0,0,100,100,0,0,1,3,0,2,85,115,260,1",
           "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    srt = []
    for scene, (start, duration) in zip(STORY["scenes"], timings):
        parts = captions(scene["voice"])
        weights = sum(len(p)+2 for p in parts)
        cursor = start
        for part in parts:
            end = cursor+(duration-0.1)*(len(part)+2)/weights
            ass.append(f"Dialogue: 0,{stamp(cursor,True)},{stamp(end,True)},Default,,0,0,0,,{part}")
            srt.append(f"{len(srt)+1}\n{stamp(cursor)} --> {stamp(end)}\n{part}\n")
            cursor = end
    (OUT/"captions.ass").write_text("\n".join(ass), encoding="utf-8-sig")
    (OUT/"captions.srt").write_text("\n".join(srt), encoding="utf-8-sig")
    # Original quiet tonal bed and soft beat; no sampled or third-party music.
    sr = 48000
    t = np.arange(sr*60, dtype=np.float64)/sr
    bed = np.zeros_like(t)
    chord_sets = [(130.81,164.81,196),(110,130.81,164.81),(87.31,110,130.81),(98,123.47,146.83)]
    for bar in range(15):
        begin = bar*4
        mask = (t>=begin)&(t<begin+4)
        local = t[mask]-begin
        env = np.minimum(local/0.7,1)*np.minimum((4-local)/0.9,1)
        for f in chord_sets[bar%4]:
            bed[mask] += 0.008*np.sin(2*np.pi*f*local)*env
    for beat in np.arange(0,60,60/92):
        mask=(t>=beat)&(t<beat+0.12)
        local=t[mask]-beat
        bed[mask]+=0.024*np.sin(2*np.pi*(62*local-90*local**2))*np.exp(-local*35)
    bed*=np.minimum(t/1.5,1)*np.minimum((60-t)/2,1)
    with wave.open(str(OUT/"original-bed.wav"),"wb") as audio:
        audio.setparams((1,2,sr,0,"NONE","not compressed"))
        audio.writeframes((np.clip(bed,-1,1)*32767).astype('<i2').tobytes())
    # Run in the output directory so subtitle paths require no Windows colon escaping.
    old = Path.cwd()
    os.chdir(OUT)
    try:
        run(["-i", "assembled.mp4", "-i", "narration.wav", "-i", "original-bed.wav", "-filter_complex",
             "[0:v]ass=captions.ass[v];[1:a]loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000[a];[a][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[m]",
             "-map", "[v]", "-map", "[m]", "-t", "60", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "BlueMusic_AIStory_60s.mp4"])
        for seconds in (1, 10, 20, 30, 40, 50, 58):
            run(["-ss", str(seconds), "-i", "BlueMusic_AIStory_60s.mp4", "-frames:v", "1", f"qa-{seconds:02}.png"])
        run(["-i", "BlueMusic_AIStory_60s.mp4", "-vn", "-c:a", "pcm_s16le", "narration-preview.wav"])
    finally:
        os.chdir(old)
    (OUT/"timings.json").write_text(json.dumps({"original_voice_seconds":total,"speed":speed,"scenes":timings},indent=2),encoding="utf-8")
    print(str(OUT/"BlueMusic_AIStory_60s.mp4"), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
