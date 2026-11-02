# -*- coding: utf-8 -*-
"""会议总结 App 后端：静态页面托管 + 语音转写 + 文本纠错 + 会议纪要生成。

设计要点：
- 未配置任何 Key 时也能启动，前端会自动降级为「浏览器实时识别 + 本地规则摘要」。
- ASR 与 LLM 都走 OpenAI 兼容协议，换供应商只改 .env，不改代码。
- v3.0：新增本地离线 ASR 引擎（faster-whisper），无需网络、免费、准确率 95%+。
- 语音转写优先级：本地引擎 > 在线 ASR > 浏览器 Web Speech API。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _res_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", _app_dir()))
    return Path(__file__).resolve().parent


BASE_DIR = _app_dir()
WEB_DIR = _res_dir() / "web"


def load_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

ASR_BASE_URL = os.getenv("ASR_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
ASR_API_KEY = os.getenv("ASR_API_KEY", "").strip()
ASR_MODEL = os.getenv("ASR_MODEL", "FunAudioLLM/SenseVoiceSmall")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

TEXT_LIMIT = 24000

app = FastAPI(title="会议总结 App")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 本地 ASR 引擎（faster-whisper）────────────────────────────────
_LOCAL_WHISPER = None
_LOCAL_WHISPER_LOADED = False
_LOCAL_WHISPER_ERROR = ""

WHISPER_CACHE = BASE_DIR / "models"


def _get_whisper():
    global _LOCAL_WHISPER, _LOCAL_WHISPER_LOADED, _LOCAL_WHISPER_ERROR
    if _LOCAL_WHISPER_LOADED:
        return _LOCAL_WHISPER
    _LOCAL_WHISPER_LOADED = True
    try:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from faster_whisper import WhisperModel
        _LOCAL_WHISPER = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
            download_root=str(WHISPER_CACHE),
        )
        return _LOCAL_WHISPER
    except ImportError:
        _LOCAL_WHISPER_ERROR = "未安装 faster-whisper，请运行: pip install faster-whisper"
    except Exception as e:
        _LOCAL_WHISPER_ERROR = f"模型加载失败: {e}"
    return None


def _local_asr_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _model_status() -> dict:
    if not _local_asr_available():
        return {"available": False, "loaded": False, "model": WHISPER_MODEL,
                "error": "未安装 faster-whisper。请运行: pip install faster-whisper"}
    model_dir = WHISPER_CACHE / f"faster-whisper-{WHISPER_MODEL}"
    if model_dir.exists():
        return {"available": True, "loaded": _LOCAL_WHISPER is not None,
                "model": WHISPER_MODEL, "error": ""}
    return {"available": True, "loaded": False, "model": WHISPER_MODEL,
            "error": f"模型 {WHISPER_MODEL} 尚未下载，首次使用时将自动下载（约 1.5GB）"}


# ── Prompt ─────────────────────────────────────────────────────────
CORRECT_PROMPT = """你是专业的中文语音转写校对员。下面是语音识别的原始输出，请逐句纠正同音错字。
常见同音混淆：求工程→需求工程，属于本体库→术语本体库，撤试用例→测试用例，大儿全→大而全，平局级→评测集。
规则：专业术语保留，补全中文标点，去除口语碎片（嗯啊那个就是说），数字→阿拉伯数字，日期统一格式。
只输出纠正后的纯文本，不要加解释或标记。"""

SYSTEM_PROMPT = """你是资深会议纪要助手。用户会给你一段会议录音整理文本。
只输出 JSON，不要加解释或代码块围栏：
{"topic":"12字以内","summary":"120-200字概述","sections":[{"title":"议题","points":["观点"]}],"decisions":["决定"],"actions":[{"task":"事项","owner":"负责人","due":"时间"}],"risks":["风险"],"keywords":["3-8个"]}
只依据原文，不要编造信息。合并口语重复，输出书面语。"""


# ── 文本工具 ─────────────────────────────────────────────────────
_CN_PUNCT_MAP = str.maketrans({
    ",": "，", ".": "。", ";": "；", ":": "：",
    "?": "？", "!": "！", "(": "（", ")": "）",
})

def normalize_cn_text(text: str) -> str:
    text = text.translate(_CN_PUNCT_MAP)
    text = re.sub(r"[ 　\t]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[嗯啊哦呃诶哎]+", "", text)
    text = re.sub(r"(那个|就是说|然后呢|所以呢|这个呢)", "", text)
    return text.strip()

def shrink_text(text: str, limit: int = TEXT_LIMIT) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    sentences = [s for s in re.split(r"(?<=[。！？!?；;\n])", text) if s.strip()]
    total = sum(len(s) for s in sentences) or 1
    ratio = limit / total
    kept: list[str] = []
    carry = 0.0
    for sentence in sentences:
        carry += len(sentence) * ratio
        if carry >= 1:
            kept.append(sentence)
            carry -= 1
    return "".join(kept)[:limit], True

def extract_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("模型未返回可解析的 JSON")


# ── Models ────────────────────────────────────────────────────────
class SummarizeRequest(BaseModel):
    text: str
    mode: str = "auto"

class CorrectRequest(BaseModel):
    text: str

class CorrectResult(BaseModel):
    text: str
    corrected: bool

class AsrResult(BaseModel):
    text: str
    provider: str


# ── 音频预处理 ────────────────────────────────────────────────────
def _preprocess_audio(audio: bytes, filename: str, mime: str):
    if "wav" in (mime or "") or "pcm" in (mime or ""):
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        tmp_in = tempfile.mktemp(suffix=".in")
        tmp_out = tmp_in + ".out.wav"
        with open(tmp_in, "wb") as f:
            f.write(audio)
        subprocess.run(
            [ffmpeg, "-y", "-i", tmp_in,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
             "-loglevel", "quiet", tmp_out],
            capture_output=True, timeout=30,
        )
        if Path(tmp_out).stat().st_size > 1024:
            with open(tmp_out, "rb") as f:
                wav_audio = f.read()
            try:
                os.unlink(tmp_in)
                os.unlink(tmp_out)
            except OSError:
                pass
            return wav_audio, "meeting_16k.wav", "audio/wav"
        try:
            os.unlink(tmp_in)
            os.unlink(tmp_out)
        except OSError:
            pass
    except Exception:
        pass
    return None


# ── LLM 调用 ─────────────────────────────────────────────────────
async def call_llm_correct(text: str) -> str:
    if not LLM_API_KEY:
        return text
    content, _ = shrink_text(text)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL, "messages": [
                {"role": "system", "content": CORRECT_PROMPT},
                {"role": "user", "content": content},
            ], "temperature": 0.1, "max_tokens": min(8000, len(content) + 2000)},
        )
    if resp.status_code >= 400:
        return text
    raw = resp.json()["choices"][0]["message"]["content"]
    corrected = raw.strip()
    corrected = re.sub(r"^```(?:text)?\s*", "", corrected)
    corrected = re.sub(r"\s*```$", "", corrected)
    return corrected if len(corrected) >= len(text) * 0.5 else text


async def call_llm_summarize(text: str, mode: str) -> dict:
    if not LLM_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 LLM_API_KEY")
    content, truncated = shrink_text(text)
    hint = "（原文过长已抽样）" if truncated else ""
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL, "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{hint}会议整理文本：\n{content}"},
            ], "temperature": 0.3, "response_format": {"type": "json_object"}},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"大模型调用失败：{resp.status_code}")
    raw = resp.json()["choices"][0]["message"]["content"]
    try:
        data = extract_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"大模型返回格式异常：{exc}") from exc
    data["_source"] = "llm"
    data["_truncated"] = truncated
    return data


# ── 本地 Whisper 转写（faster-whisper）────────────────────────────
async def _transcribe_local(audio: bytes, filename: str, mime: str) -> AsrResult:
    model = _get_whisper()
    if model is None:
        raise HTTPException(status_code=400, detail=_LOCAL_WHISPER_ERROR or "本地语音引擎不可用")

    processed = _preprocess_audio(audio, filename, mime)
    if processed is not None:
        audio, _fn, _m = processed

    suffix = ".wav" if "wav" in (mime or "") else ".webm"
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(audio)

        segments, info = model.transcribe(
            tmp_path, language="zh", beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
        )
        texts = [seg.text.strip() for seg in segments]
        raw_text = " ".join(texts)
        cleaned = normalize_cn_text(raw_text)
        return AsrResult(text=cleaned, provider=f"whisper-{WHISPER_MODEL}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"本地语音转写失败: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── 在线 ASR ──────────────────────────────────────────────────────
async def _transcribe_online(audio: bytes, filename: str, mime: str) -> AsrResult:
    if not ASR_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 ASR_API_KEY")

    processed = _preprocess_audio(audio, filename, mime)
    if processed is not None:
        audio, filename, mime = processed

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(
                f"{ASR_BASE_URL}/audio/transcriptions",
                headers={"Authorization": f"Bearer {ASR_API_KEY}"},
                files={"file": (filename, audio, mime)},
                data={"model": ASR_MODEL, "language": "zh", "response_format": "verbose_json"},
            )
            if resp.status_code in (400, 422):
                resp = await client.post(
                    f"{ASR_BASE_URL}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {ASR_API_KEY}"},
                    files={"file": (filename, audio, mime)},
                    data={"model": ASR_MODEL},
                )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="语音转写超时")

    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"转写失败：{resp.status_code}")

    result = resp.json()
    raw_text = result.get("text", "")
    if not raw_text and "segments" in result:
        raw_text = " ".join(s.get("text", "") for s in result["segments"])
    return AsrResult(text=normalize_cn_text(raw_text), provider=ASR_MODEL)


# ── 路由 ─────────────────────────────────────────────────────────
@app.get("/api/config")
async def get_config() -> dict:
    ms = _model_status()
    return {
        "asr": bool(ASR_API_KEY),
        "llm": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL if LLM_API_KEY else "",
        "asr_model": ASR_MODEL if ASR_API_KEY else "",
        "local_asr": ms,
    }

@app.get("/api/model/status")
async def model_status() -> dict:
    return _model_status()

@app.get("/api/model/preload")
async def model_preload() -> dict:
    if not _local_asr_available():
        return {"ok": False, "error": "未安装 faster-whisper"}
    try:
        _get_whisper()
        return {"ok": True, "model": WHISPER_MODEL}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/asr", response_model=AsrResult)
async def transcribe(file: UploadFile = File(...), engine: str = "auto") -> AsrResult:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="音频内容为空")
    filename = (file.filename or "audio.webm")
    mime = file.content_type or "audio/webm"

    if engine == "auto":
        if _local_asr_available():
            try:
                return await _transcribe_local(audio, filename, mime)
            except HTTPException:
                pass
        if ASR_API_KEY:
            return await _transcribe_online(audio, filename, mime)
        if _local_asr_available():
            return await _transcribe_local(audio, filename, mime)
        raise HTTPException(status_code=400, detail="未配置任何语音转写引擎")
    elif engine == "local":
        return await _transcribe_local(audio, filename, mime)
    elif engine == "online":
        return await _transcribe_online(audio, filename, mime)
    raise HTTPException(status_code=400, detail=f"未知引擎: {engine}")

@app.post("/api/correct", response_model=CorrectResult)
async def correct_text(req: CorrectRequest) -> CorrectResult:
    text = (req.text or "").strip()
    if not text:
        return CorrectResult(text="", corrected=False)
    if len(text) < 10:
        return CorrectResult(text=normalize_cn_text(text), corrected=False)
    if not LLM_API_KEY:
        return CorrectResult(text=normalize_cn_text(text), corrected=False)
    corrected = await call_llm_correct(text)
    return CorrectResult(text=corrected, corrected=corrected != text)

@app.post("/api/summarize")
async def summarize(req: SummarizeRequest) -> dict:
    text = (req.text or "").strip()
    if len(text) < 40:
        raise HTTPException(status_code=400, detail="会议内容太短，至少 40 个字再生成纪要")
    text = normalize_cn_text(text)
    return await call_llm_summarize(text, req.mode)

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))