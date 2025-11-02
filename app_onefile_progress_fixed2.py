
import os, sys, uuid, time, json, queue, threading, tempfile, subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, StreamingResponse

APP_TITLE = "TS → MP4 Converter (Onefile + Progress)"
APP_VERSION = "2.1.2"

INDEX_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>TS → MP4 Converter</title><style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:24px;max-width:900px;margin:0 auto}
header{margin-bottom:16px}.drop{border:2px dashed #999;border-radius:10px;padding:24px;text-align:center;color:#555}
ul{list-style:none;padding:0}li{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #eee}
button{cursor:pointer}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.hidden{display:none}
.out{margin-top:16px;padding:12px;background:#fafafa;border:1px solid #eee;border-radius:8px}.files{margin-top:12px}
.small{font-size:12px;color:#666}code{background:#f2f2f2;padding:2px 4px;border-radius:4px}input[type=text]{min-width:280px}
.bar{width:100%;height:12px;background:#eee;border-radius:8px;overflow:hidden}.bar>div{height:100%;width:0%;background:#4b8cf0;transition:width .2s linear}
.indet{position:relative;overflow:hidden}.indet:before{content:"";position:absolute;left:-40%;width:40%;top:0;bottom:0;background:#4b8cf0;animation:ind 1s infinite}
@keyframes ind{0%{left:-40%}100%{left:100%}}
#fileInput{display:none}
.label-btn{padding:8px 12px;border:1px solid #ccc;border-radius:8px;cursor:pointer;display:inline-block;background:#fff}
</style></head><body>
<header><h1>Convert/Merge .ts → .mp4</h1><p class="small">Pick or drop .ts files, reorder them, set output name and folder, then convert. FFmpeg is bundled.</p></header>
<div class="row">
  <input type="file" id="fileInput" multiple accept=".ts,video/mp2t" />
  <label for="fileInput" id="fileBtn" class="label-btn">Select files…</label>
  <span id="fileHint" class="small">No files selected</span>
  <input type="text" id="outputName" placeholder="Output filename (e.g., movie.mp4)" />
</div>
<div class="row"><input type="text" id="outputDir" placeholder="Output folder (e.g., C:\\\\Users\\\\me\\\\Videos or /Users/me/Videos)" /><button id="btnConvert">Convert</button></div>
<div class="drop" id="dropZone">Drop .ts files here</div>
<div class="files"><h3>Selected files</h3><ul id="fileList"></ul></div>
<div class="out hidden" id="progressBox"><div><strong>Status:</strong> <span id="statusText">Starting…</span></div><div class="bar" id="progressBarWrapper"><div id="progressLine"></div></div><div class="bar indet hidden" id="indBar"></div><div class="small"><span id="timeInfo"></span></div></div>
<div class="out hidden" id="resultBox"><strong>Done!</strong> <a id="downloadLink" href="#" download>Download MP4</a></div>
<script>
const fileInput=document.getElementById('fileInput'),fileBtn=document.getElementById('fileBtn'),fileHint=document.getElementById('fileHint'),fileList=document.getElementById('fileList'),dropZone=document.getElementById('dropZone'),btnConvert=document.getElementById('btnConvert'),outputName=document.getElementById('outputName'),outputDir=document.getElementById('outputDir'),progressBox=document.getElementById('progressBox'),statusText=document.getElementById('statusText'),progressLine=document.getElementById('progressLine'),progressBarWrapper=document.getElementById('progressBarWrapper'),indBar=document.getElementById('indBar'),resultBox=document.getElementById('resultBox'),downloadLink=document.getElementById('downloadLink'),timeInfo=document.getElementById('timeInfo');let files=[];
function renderList(){fileList.innerHTML='';files.forEach((f,i)=>{const li=document.createElement('li');li.innerHTML=`<span style="flex:1">${f.name}</span><button data-act="up" data-i="${i}">↑</button><button data-act="down" data-i="${i}">↓</button><button data-act="remove" data-i="${i}">✕</button>`;fileList.appendChild(li);});fileHint.textContent=files.length?`${files.length} file(s) selected`:'No files selected';}
fileList.addEventListener('click',e=>{const btn=e.target.closest('button');if(!btn)return;const i=parseInt(btn.dataset.i,10),act=btn.dataset.act;if('remove'===act)files.splice(i,1);if('up'===act&&i>0)[files[i-1],files[i]]=[files[i],files[i-1]];if('down'===act&&i<files.length-1)[files[i+1],files[i]]=[files[i],files[i+1]];renderList();});
fileInput.addEventListener('change',e=>{files=[...files,...e.target.files];renderList();});
['dragenter','dragover','dragleave','drop'].forEach(n=>{dropZone.addEventListener(n,e=>{e.preventDefault();e.stopPropagation();},!1);});
dropZone.addEventListener('drop',e=>{files=[...files,...e.dataTransfer.files];renderList();});
function setIndeterminate(on){indBar.classList.toggle('hidden',!on);progressBarWrapper.classList.toggle('hidden',on);}
btnConvert.addEventListener('click',async()=>{if(0===files.length){alert('Please add at least one .ts file');return;}const fd=new FormData();files.forEach(f=>fd.append('files',f));if(outputName.value.trim())fd.append('output_name',outputName.value.trim());if(outputDir.value.trim())fd.append('output_dir',outputDir.value.trim());btnConvert.disabled=!0;btnConvert.textContent='Uploading…';progressBox.classList.remove('hidden');resultBox.classList.add('hidden');statusText.textContent='Uploading…';try{const res=await fetch('/api/convert-start',{method:'POST',body:fd});if(!res.ok){const err=await res.json().catch(()=>({detail:'Unknown error'}));throw new Error(err.detail||'Error');}
const data=await res.json(),jobId=data.job_id;statusText.textContent='Processing…';setIndeterminate(!0);const es=new EventSource(`/api/convert-progress/${jobId}`);es.onmessage=e=>{const msg=JSON.parse(e.data);if('progress'===msg.type){null!=msg.percent?(setIndeterminate(!1),progressLine.style.width=(100*msg.percent).toFixed(1)+'%'):setIndeterminate(!0);timeInfo.textContent=msg.detail||'';}else if('done'===msg.type){es.close();btnConvert.disabled=!1;btnConvert.textContent='Convert';statusText.textContent='Completed';progressLine.style.width='100%';resultBox.classList.remove('hidden');downloadLink.href=msg.download_url;downloadLink.textContent=msg.filename;}else if('error'===msg.type){es.close();btnConvert.disabled=!1;btnConvert.textContent='Convert';statusText.textContent='Error';alert(msg.detail||'Processing error');}};}catch(err){alert(err.message);btnConvert.disabled=!1;btnConvert.textContent='Convert';statusText.textContent='Error';}});
</script></body></html>"""

def _resolve_ffmpeg() -> str:
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "ffbin" / exe_name
        if candidate.exists():
            return str(candidate)
    try:
        import imageio_ffmpeg as iioff
        return iioff.get_ffmpeg_exe()
    except Exception:
        pass
    return "ffmpeg"

def _resolve_ffprobe(ffmpeg_path: str) -> Optional[str]:
    p = Path(ffmpeg_path)
    if p.name.lower().startswith("ffmpeg"):
        probe = p.with_name("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
        if probe.exists():
            return str(probe)
    return "ffprobe"

FFMPEG = _resolve_ffmpeg()
FFPROBE = _resolve_ffprobe(FFMPEG)

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)

def _ffprobe_duration(path: Path) -> Optional[float]:
    try:
        out = subprocess.check_output([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                       "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                                      stderr=subprocess.STDOUT, text=True)
        return float(out.strip())
    except Exception:
        return None

ProgressEvent = Dict[str, Any]
PROGRESS_QUEUES: Dict[str, "queue.Queue[ProgressEvent]"] = {}
RESULTS: Dict[str, Dict[str, Any]] = {}

def sse_stream(q: "queue.Queue[ProgressEvent]"):
    yield b":ok\n\n"
    while True:
        try:
            item = q.get(timeout=1.0)
        except queue.Empty:
            yield b":hb\n\n"
            continue
        yield f"data: {json.dumps(item)}\n\n".encode("utf-8")
        if item.get("type") in ("done", "error"):
            break

def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600); m = int((seconds % 3600) // 60); s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def _pump_progress(proc: subprocess.Popen, q: "queue.Queue[ProgressEvent]", total_duration: Optional[float]):
    last_emit = 0.0
    seen = 0.0
    if not proc.stdout:
        return
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("out_time_ms="):
            try:
                out_ms = int(line.split("=",1)[1])
                seen = out_ms / 1_000_000.0
            except Exception:
                continue
            percent = None
            detail = None
            if total_duration and total_duration > 0:
                percent = min(0.999, seen / total_duration)
                detail = f"{_fmt_time(seen)} / {_fmt_time(total_duration)}"
            else:
                detail = f"{_fmt_time(seen)} elapsed"
            now = time.time()
            if now - last_emit > 0.2:
                q.put({"type":"progress", "percent": percent, "detail": detail})
                last_emit = now
        elif line.startswith("progress=") and line.endswith("end"):
            percent = 1.0 if (total_duration and total_duration>0) else None
            q.put({"type":"progress", "percent": percent, "detail": "Finalizing…"})

def _convert_thread(job_id: str, saved_paths: List[Path], output_path: Path, total_duration: Optional[float]):
    q = PROGRESS_QUEUES[job_id]
    try:
        if len(saved_paths) == 1:
            cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1",
                   "-i", str(saved_paths[0]), "-c", "copy", "-bsf:a", "aac_adtstoasc", str(output_path)]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            _pump_progress(proc, q, total_duration)
            code = proc.wait()
            if code != 0:
                err = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"ffmpeg exited with code {code}: {err}")
        else:
            with tempfile.TemporaryDirectory() as td:
                list_file = Path(td) / "list.txt"
                with list_file.open("w", encoding="utf-8", newline="\n") as f:
                    for p in saved_paths:
                        path_for_ff = str(p.resolve()).replace("\\", "/")
                        f.write(f"file '{path_for_ff}'\n")
                cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1",
                       "-f", "concat", "-safe", "0", "-i", str(list_file),
                       "-c", "copy", "-bsf:a", "aac_adtstoasc", str(output_path)]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
                _pump_progress(proc, q, total_duration)
                code = proc.wait()
                if code != 0:
                    err = proc.stderr.read() if proc.stderr else ""
                    raise RuntimeError(f"ffmpeg exited with code {code}: {err}")
        RESULTS[job_id] = {"download_url": f"/download?path={output_path.as_posix()}", "filename": output_path.name}
        q.put({"type":"done", **RESULTS[job_id]})
    except Exception as e:
        q.put({"type":"error", "detail": str(e)})

@app.post("/api/convert-start")
async def convert_start(files: List[UploadFile] = File(...), output_name: Optional[str] = Form(default="output.mp4"), output_dir: Optional[str] = Form(default="")):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one .ts file")
    if not output_name.lower().endswith(".mp4"):
        output_name = f"{output_name}.mp4"

    if output_dir:
        out_dir = Path(output_dir).expanduser()
        try: out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e: raise HTTPException(status_code=400, detail=f"Cannot create output folder: {e}")
    else:
        out_dir = Path.cwd() / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / output_name
    i = 1; base = output_path.stem
    while output_path.exists():
        output_path = out_dir / f"{base}_{i}.mp4"; i += 1

    td = tempfile.TemporaryDirectory()
    tmp_dir = Path(td.name)
    saved_paths: List[Path] = []
    total_duration: Optional[float] = 0.0
    have_any = False
    for idx, uf in enumerate(files):
        fname = uf.filename or f"input_{idx}.ts"
        if not fname.lower().endswith(".ts"): fname = Path(fname).stem + ".ts"
        safe = "".join(c for c in fname if c.isalnum() or c in (" ",".","_","-",".")).strip()
        dest = tmp_dir / f"{idx:04d}_{safe}"
        content = await uf.read()
        dest.write_bytes(content)
        saved_paths.append(dest)
        dur = _ffprobe_duration(dest)
        if dur: total_duration += dur; have_any = True
    if not have_any: total_duration = None

    job_id = str(uuid.uuid4())
    q: "queue.Queue[dict]" = queue.Queue()
    PROGRESS_QUEUES[job_id] = q

    th = threading.Thread(target=_convert_thread, args=(job_id, saved_paths, output_path, total_duration), daemon=True)
    th.start()

    def _cleanup():
        th.join()
        try: td.cleanup()
        except: pass
    threading.Thread(target=_cleanup, daemon=True).start()

    return {"job_id": job_id, "filename": output_path.name}

@app.get("/api/convert-progress/{job_id}")
def convert_progress(job_id: str):
    q = PROGRESS_QUEUES.get(job_id)
    if not q: raise HTTPException(status_code=404, detail="Invalid job id")
    return StreamingResponse(sse_stream(q), media_type="text/event-stream")

@app.get("/download")
def download_file(path: str):
    p = Path(path)
    if not p.exists() or p.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(p), media_type="video/mp4", filename=p.name)

@app.get("/api/ffmpeg-path", response_class=PlainTextResponse)
def ffmpeg_path():
    return FFMPEG

def main():
    import uvicorn, webbrowser
    def open_browser():
        try: webbrowser.open("http://127.0.0.1:8000")
        except: pass
    threading.Timer(1.0, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
