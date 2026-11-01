"""通过本地代理完成一次真实语音对话，验证前端要走的链路。"""

import asyncio, base64, json, subprocess, tempfile
from pathlib import Path
import websockets

FFMPEG = "D:/graduation_design/tools/ffmpeg/node_modules/ffmpeg-static/ffmpeg.exe"
PROXY = "ws://127.0.0.1:8081/api/v1/voice/ws"
ROOT = Path("D:/graduation_design/backend")


def speech() -> bytes:
    work = Path(tempfile.mkdtemp()); txt, ps, wav, pcm = work/"t.txt", work/"t.ps1", work/"t.wav", work/"t.pcm"
    txt.write_text("你好，我叫王明博，2026 年毕业，做过订单系统。", encoding="utf-8")
    ps.write_text("Add-Type -AssemblyName System.Speech\n$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
                  "$s.SelectVoice('Microsoft Huihui Desktop')\n"
                  f"$s.SetOutputToWaveFile('{wav.as_posix()}')\n"
                  f"$t = Get-Content -Raw -Encoding UTF8 '{txt.as_posix()}'\n$s.Speak($t)\n$s.Dispose()\n", encoding="utf-8")
    subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ps)], check=True, capture_output=True)
    subprocess.run([FFMPEG,"-y","-i",str(wav),"-f","s16le","-ac","1","-ar","16000",str(pcm)], check=True, capture_output=True)
    return pcm.read_bytes()


async def main() -> None:
    pcm = speech(); audio = bytearray(); texts = []
    async with websockets.connect(PROXY, max_size=None, open_timeout=20) as ws:
        await ws.send(json.dumps({"type":"session.create","session":{"model":"1.2.6.1",
            "instructions":"你是中文面试官，候选人说完后回应一句并追问一个具体问题，40 字以内。",
            "audio":{"input":{"format":{"type":"pcm","rate":16000}},
                     "output":{"format":{"type":"pcm_s16le","rate":24000},"voice":"zh_female_xiaohe_jupiter_bigtts"}}},
            "extension":{"asr":{"extra":{}},"tts":{},"dialog":{}}}, ensure_ascii=False))
        print("session:", json.loads(await asyncio.wait_for(ws.recv(), 15))["type"])

        async def reader():
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), 25)
                except asyncio.TimeoutError:
                    return
                ev = json.loads(raw)
                t = ev.get("type","")
                if t == "response.output_text.done":
                    texts.append(ev.get("text",""))
                    print("REPLY:", ev.get("text"))
                elif t == "response.output_audio.delta":
                    audio.extend(base64.b64decode(ev.get("delta","")))
                elif t.endswith("transcription.completed"):
                    print("ASR:", ev.get("transcript"))
                elif t == "error":
                    print("ERR:", json.dumps(ev, ensure_ascii=False)[:150])

        task = asyncio.create_task(reader())
        for i in range(0, len(pcm), 640):
            await ws.send(json.dumps({"type":"input_audio_buffer.append","audio":base64.b64encode(pcm[i:i+640]).decode()}))
            await asyncio.sleep(0.02)
        for _ in range(50):
            await ws.send(json.dumps({"type":"input_audio_buffer.append","audio":base64.b64encode(b"\x00"*640).decode()}))
            await asyncio.sleep(0.02)
        await ws.send(json.dumps({"type":"input_audio_buffer.commit"}))
        await asyncio.sleep(20)
        task.cancel()
    print("audio bytes:", len(audio), "| replies:", len(texts))
    if audio:
        raw = ROOT/".tmp-proxy.pcm"; raw.write_bytes(bytes(audio))
        subprocess.run([FFMPEG,"-y","-f","s16le","-ar","24000","-ac","1","-i",str(raw),str(ROOT/".tmp-proxy.wav")], check=True, capture_output=True)
        print("wav:", (ROOT/".tmp-proxy.wav").stat().st_size)

asyncio.run(main())
