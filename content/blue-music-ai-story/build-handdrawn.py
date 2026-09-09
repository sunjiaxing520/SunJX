"""Two short voice auditions with no fictional people or invented UI."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import wave

import edge_tts
import imageio_ffmpeg

HERE = Path(__file__).parent
SPEC = json.loads((HERE/'handdrawn-preview.json').read_text(encoding='utf-8'))
OUT = Path(SPEC['output'])
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run(args):
    result = subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y',*map(str,args)],
                            capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-1800:])


def timecode(t):
    cs = round(t*100)
    s, fraction = divmod(cs,100)
    return f'0:{s//60:02}:{s%60:02}.{fraction:02}'


async def main():
    (OUT/'audio').mkdir(parents=True,exist_ok=True)
    for voice in SPEC['voices']:
        name=voice['id']
        lengths=[]
        for i,scene in enumerate(SPEC['scenes']):
            mp3=OUT/'audio'/f'{name}-{i}.mp3'
            if not mp3.exists():
                print(f"Voice {name}, phrase {i+1}/3",flush=True)
                for attempt in range(3):
                    try:
                        temp=mp3.with_suffix('.part')
                        await edge_tts.Communicate(scene['voice'],voice['name'],rate='-3%',
                            connect_timeout=15,receive_timeout=25,
                            proxy=os.getenv('VIDEO_TTS_PROXY')).save(str(temp))
                        temp.replace(mp3)
                        break
                    except Exception:
                        if attempt==2:
                            raise
                        await asyncio.sleep(2+attempt)
            wav=mp3.with_suffix('.wav')
            run(['-i',mp3,'-ar','48000','-ac','1',wav])
            with wave.open(str(wav)) as a:
                lengths.append(a.getnframes()/a.getframerate())
        # Keep a conversational pace: do not squeeze a long voice into ten seconds.
        total=sum(lengths)
        target=max(10,round((total+0.45)*30)/30)
        speed=total/(target-0.45)
        pcm_parts=[]
        timings=[]
        cursor=0
        for i,length in enumerate(lengths):
            duration=round((length/speed+0.15)*30)/30 if i<2 else target-cursor
            timings.append((cursor,duration))
            processed=OUT/'audio'/f'{name}-{i}-timed.wav'
            run(['-i',OUT/'audio'/f'{name}-{i}.wav','-af',f'atempo={speed:.8f},apad',
                 '-t',f'{duration:.8f}','-ar','48000','-ac','1',processed])
            with wave.open(str(processed)) as a:
                data=a.readframes(a.getnframes())
                expected=round(duration*48000)*2
                pcm_parts.append((data+b'\0'*expected)[:expected])
            zoom="zoompan=z='min(zoom+0.00015,1.04)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30"
            run(['-loop','1','-framerate','30','-i',OUT/'frames'/f'{i}.png','-vf',zoom,
                 '-t',duration,'-c:v','libx264','-preset','veryfast','-crf','20',
                 '-pix_fmt','yuv420p','-an','-threads','2',OUT/f'{name}-scene-{i}.mp4'])
            cursor+=duration
        with wave.open(str(OUT/f'voice-{name}.wav'),'wb') as a:
            a.setparams((1,2,48000,0,'NONE','not compressed'))
            a.writeframes(b''.join(pcm_parts))
        concat=OUT/f'{name}-concat.txt'
        concat.write_text('\n'.join(f"file '{name}-scene-{i}.mp4'" for i in range(3)),encoding='utf-8')
        run(['-f','concat','-safe','0','-i',concat,'-c','copy',OUT/f'{name}-silent.mp4'])
        subtitles=[
            '[Script Info]','ScriptType: v4.00+','PlayResX: 1080','PlayResY: 1920',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
            'Style: Default,Microsoft YaHei,43,&H00232A30,&H00232A30,&H00F6F7F9,&H00F6F7F9,1,0,0,0,100,100,0,0,1,3,0,2,95,115,230,1',
            '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
        ]
        for scene,(start,duration) in zip(SPEC['scenes'],timings):
            text=scene['voice'].replace('。','').replace('，','，')
            if len(text)>17:
                cut=text.find('，')+1
                text=text[:cut]+r'\N'+text[cut:]
            subtitles.append(f'Dialogue: 0,{timecode(start)},{timecode(start+duration-0.08)},Default,,0,0,0,,{text}')
        (OUT/f'{name}.ass').write_text('\n'.join(subtitles),encoding='utf-8-sig')
        old=Path.cwd()
        os.chdir(OUT)
        try:
            run(['-i',f'{name}-silent.mp4','-i',f'voice-{name}.wav','-vf',f'ass={name}.ass',
                 '-af','loudnorm=I=-16:TP=-1.5:LRA=9','-t',target,'-c:v','libx264',
                 '-preset','veryfast','-crf','20','-threads','2','-pix_fmt','yuv420p',
                 '-c:a','aac','-ar','48000','-b:a','192k','-movflags','+faststart',f'Handdrawn_Opening_{name}.mp4'])
            for second in (1,4,8):
                run(['-ss',second,'-i',f'Handdrawn_Opening_{name}.mp4','-frames:v','1',f'qa-{name}-{second}.png'])
        finally:
            os.chdir(old)
        (OUT/f'{name}-timings.json').write_text(json.dumps({'voice':voice['name'],'duration':target,'speed':speed,'timings':timings},indent=2),encoding='utf-8')
        print(f'{name}: {target:.2f} seconds, rendered',flush=True)


if __name__=='__main__':
    asyncio.run(main())
