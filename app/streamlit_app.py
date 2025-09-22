import asyncio, base64, io, re, time
from typing import List
import streamlit as st

try:
    import edge_tts
except:
    edge_tts = None
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None
    
st.set_page_config(page_title="English TTS Coach", page_icon="🎙️", layout="centered")
st.title("🎙️ English TTS Coach — MVP")

VOICE_PRESETS = [
    {"label": "Aria · US (clear, friendly — female)",  "id": "en-US-AriaNeural"},
    {"label": "Guy · US (neutral, baritone — male)",   "id": "en-US-GuyNeural"},
    {"label": "Jenny · US (bright, conversational)",   "id": "en-US-JennyNeural"},
    {"label": "Libby · UK (articulate RP-ish — f)",    "id": "en-GB-LibbyNeural"},
    {"label": "Natasha · AU (warm — female)",          "id": "en-AU-NatashaNeural"},
    {"label": "Neerja · IN (exam-neutral — female)",   "id": "en-IN-NeerjaNeural"},
]

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

def chunk_text(text: str, max_chars: int = 2000):
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= max_chars:
            buf = f"{buf} {s}".strip()
        else:
            if buf: chunks.append(buf)
            buf = s
    if buf: chunks.append(buf)
    return chunks

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
    # naive concat to avoid ffmpeg dependency
    return b"".join(parts)

with st.sidebar:
    st.header("Input & Voice")
    raw = st.text_area("Paste your text (KR/EN)", height=220,
                       placeholder="여기에 영어/한국어 텍스트를 붙여 넣으세요…")
    use_translation = st.checkbox("Free-translate to English (deep-translator)", value=False)
    
    labels = [p["label"] for p in VOICE_PRESETS]
    choice = st.selectbox("Voice", labels, index=0)
    custom = st.text_input("Or custom Edge voice (optional)")
    vid = next((p["id"] for p in VOICE_PRESETS if p["label"] == choice), VOICE_PRESETS[0]["id"])
    if custom.strip(): vid = custom.strip()

    st.subheader("Synthesis params")
    rate_val  = st.slider("Rate (%)",  -50, 50, 0)
    pitch_val = st.slider("Pitch (Hz)", -300, 300, 0)
    rate_str  = f"{rate_val:+d}%"
    pitch_str = f"{pitch_val:+d}Hz"

    go = st.button("🎧 Generate")

st.write("#### Player & AB Loop (hotkeys: **A** = set A, **B** = set B, **R** = repeat toggle)")

if "audio_b64" not in st.session_state: st.session_state.audio_b64 = None

if go:
    if not raw.strip():
        st.warning("Paste some text first.")
    else:
        # ✅ 여기서 final_text 생성
        final_text = raw
        if use_translation and raw.strip():
            final_text = free_translate_to_english(raw)

        with st.spinner("Synthesizing…"):
            mp3_bytes = synth_all(final_text, vid, rate_str, pitch_str)
        st.success("Done!")
        st.session_state.audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")


audio_b64 = st.session_state.audio_b64
if audio_b64:
    from streamlit.components.v1 import html
    html(f"""
    <div style="font-family: ui-sans-serif; line-height:1.4">
      <audio id="player" controls src="data:audio/mp3;base64,{audio_b64}" style="width:100%"></audio>
      <div style="margin-top:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap">
        <button id="setA">Set A</button>
        <button id="setB">Set B</button>
        <label>Repeats:
          <input type="number" id="repeatN" value="5" min="1" max="50" style="width:60px">
        </label>
        <button id="startLoop">▶ Start Loop</button>
        <span id="info" style="margin-left:8px; opacity:.8"></span>
      </div>
    </div>
    <script>
    (function() {{
      const audio = document.getElementById('player');
      const btnA = document.getElementById('setA');
      const btnB = document.getElementById('setB');
      const btnStart = document.getElementById('startLoop');
      const info = document.getElementById('info');
      const repeatN = document.getElementById('repeatN');

      let A = 0, B = 0, looping = false, left = 0;

      function fmt(t) {{
        const m = Math.floor(t/60), s = Math.floor(t%60).toString().padStart(2,'0');
        return m+":"+s;
      }}

      btnA.onclick = () => {{ A = audio.currentTime; info.textContent = `A = `+fmt(A); }};
      btnB.onclick = () => {{ B = audio.currentTime; info.textContent = `A = `+fmt(A)+`  |  B = `+fmt(B); }};

      // Hotkeys: A / B / R
      window.addEventListener('keydown', (e) => {{
        if (['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) return;
        if (e.key.toLowerCase() === 'a') btnA.click();
        if (e.key.toLowerCase() === 'b') btnB.click();
        if (e.key.toLowerCase() === 'r') btnStart.click();
      }});

      btnStart.onclick = () => {{
        if (!looping) {{
          if (B <= A) {{ alert('Set A then B (B must be > A)'); return; }}
          left = parseInt(repeatN.value || '1', 10);
          looping = true; btnStart.textContent = '⏹ Stop Loop';
          audio.currentTime = A; audio.play();
          info.textContent = `Looping `+left+`× from `+fmt(A)+` to `+fmt(B);
        }} else {{
          looping = false; btnStart.textContent = '▶ Start Loop';
          info.textContent = 'Loop stopped';
        }}
      }};

      audio.addEventListener('timeupdate', () => {{
        if (!looping) return;
        if (audio.currentTime >= B) {{
          left -= 1;
          if (left <= 0) {{
            looping = false; btnStart.textContent = '▶ Start Loop';
            info.textContent = 'Done';
            audio.pause();
          }} else {{
            audio.currentTime = A; audio.play();
            info.textContent = `Looping `+left+`× left`;
          }}
        }}
      }});
    }})();
    </script>
    """, height=180)
else:
    st.info("Paste text → choose voice → Generate. Then set **A/B** and press **Start Loop** (hotkeys: A/B/R).")
