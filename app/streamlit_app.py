"""
TTS Diary Studio — Edge-TTS Edition (Free)

Paste text ➜ (optional) translate to English ➜ synthesize MP3 with Microsoft Edge TTS

Run locally:
  pip install --upgrade streamlit edge-tts deep-translator
  streamlit run tts_diary_studio_edge.py

Notes:
- Edge-TTS expects rate in % (e.g. "+10%") and pitch in Hz (e.g. "+20Hz").
- This layout puts **Input & Voice** on the main area (larger), not in the sidebar.
"""

import asyncio
import base64
import io
import re
import time
from typing import List

import streamlit as st

try:
    import edge_tts
except Exception:
    edge_tts = None

# optional translator (more stable than googletrans)
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

st.set_page_config(page_title="TTS Diary Studio — Edge", page_icon="🎙️", layout="wide")
st.title("🎙️ TTS Diary Studio — Edge-TTS Edition")
st.caption("Paste diary text → (optional) translate → choose voice & tone → Generate → listen & download")

# ----------------------------
# Helpers
# ----------------------------
SAMPLE_SENTENCE = (
    "I wake up early, review my goals, and build tiny habits that compound over time."
)

VOICE_PRESETS = [
    {"label": "Aria · US (clear, friendly — female)",  "id": "en-US-AriaNeural"},
    {"label": "Guy · US (neutral, baritone — male)",   "id": "en-US-GuyNeural"},
    {"label": "Jenny · US (bright, conversational)",   "id": "en-US-JennyNeural"},
    {"label": "Libby · UK (articulate RP-ish — f)",    "id": "en-GB-LibbyNeural"},
    {"label": "Natasha · AU (warm — female)",          "id": "en-AU-NatashaNeural"},
    {"label": "Neerja · IN (exam-neutral — female)",   "id": "en-IN-NeerjaNeural"},
]

def chunk_text(text: str, max_chars: int = 2000) -> List[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= max_chars:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks

@st.cache_data(show_spinner=False)
def free_translate_to_english(text: str) -> str:
    if not text.strip():
        return ""
    if GoogleTranslator is None:
        return text
    try:
        return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        return text

async def edge_tts_once(text: str, voice: str, rate: str, pitch: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    mp3_bytes = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes.extend(chunk["data"])
    return bytes(mp3_bytes)

def synth_all(text: str, voice_id: str, rate: str, pitch: str) -> bytes:
    parts = []
    for c in chunk_text(text):
        parts.append(asyncio.run(edge_tts_once(c, voice_id, rate, pitch)))
    # naive concat to avoid external deps
    return b"".join(parts)

# ----------------------------
# Layout — Input & Voice on MAIN (bigger)
# ----------------------------
left, right = st.columns([3, 2])

with left:
    st.subheader("Input & Voice")
    raw = st.text_area(
        "Paste your text (KR/EN)", height=320,
        placeholder="여기에 영어/한국어 텍스트를 붙여 넣으세요…",
    )
    use_translation = st.checkbox("Translate to English (deep-translator)", value=False)

    labels = [p["label"] for p in VOICE_PRESETS]
    choice = st.selectbox("Voice", labels, index=0)
    custom = st.text_input("Or custom Edge voice (optional)", value="")
    voice_id = next((p["id"] for p in VOICE_PRESETS if p["label"] == choice), VOICE_PRESETS[0]["id"])
    if custom.strip():
        voice_id = custom.strip()

    st.markdown("**Tone controls (synthesis)**")
    c1, c2 = st.columns(2)
    with c1:
        rate_val  = st.slider("Rate (%)",  -50, 50, 0)
    with c2:
        pitch_val = st.slider("Pitch (Hz)", -300, 300, 0)
    rate_str  = f"{rate_val:+d}%"
    pitch_str = f"{pitch_val:+d}Hz"

    generate = st.button("🎧 Generate MP3", use_container_width=True)

with right:
    st.subheader("Preview & Export")
    if st.button("🔊 Preview sample", use_container_width=True):
        try:
            audio = asyncio.run(edge_tts_once(SAMPLE_SENTENCE, voice_id, "+0%", "+0Hz"))
            st.audio(audio, format="audio/mp3")
        except Exception as e:
            st.error(str(e))
    outname = st.text_input("Output file name", value=f"diary_{int(time.time())}")

st.divider()

# ----------------------------
# Synthesize & show player
# ----------------------------
if "audio_b64" not in st.session_state:
    st.session_state.audio_b64 = None

if generate:
    if not raw.strip():
        st.warning("Paste some text first.")
    else:
        final_text = raw
        if use_translation:
            final_text = free_translate_to_english(raw)
        with st.spinner("Synthesizing…"):
            mp3_bytes = synth_all(final_text, voice_id, rate_str, pitch_str)
        st.success("Done!")
        st.session_state.audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")

if st.session_state.audio_b64:
    audio_b64 = st.session_state.audio_b64
    st.audio(base64.b64decode(audio_b64), format="audio/mp3")
    st.download_button(
        "⬇️ Download MP3",
        data=base64.b64decode(audio_b64),
        file_name=f"{outname}.mp3",
        mime="audio/mpeg",
    )

st.info("Tip: Input & Voice가 메인에 크게 배치되었습니다. 번역은 deep-translator 기반이며, 합성 파라미터는 Rate(%) / Pitch(Hz) 규격입니다.")
