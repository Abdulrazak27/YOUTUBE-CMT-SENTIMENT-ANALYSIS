import streamlit as st
import os
import csv
import json
import requests
from Senti import extract_video_id, analyze_sentiment, bar_chart, plot_sentiment
from YoutubeCommentScrapper import (
    save_video_comments_to_csv, get_channel_info,
    youtube, get_channel_id, get_video_stats
)

# ── Groq AI setup (free, no quota issues) ─────────────────────────────────────
try:
    GROQ_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
except Exception:
    GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YT Sentiment + AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="auto"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html, body, [class*="css"] {
    background-color: #0a0a0f !important;
    color: #e8e8f0 !important;
    font-family: 'Syne', sans-serif;
}
.stTextInput > div > div > input {
    background: #13131a !important;
    border: 1px solid #2a2a3a !important;
    color: #e8e8f0 !important;
    border-radius: 8px !important;
}
.stButton > button {
    background: #7c6aff !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
}
.ai-card {
    background: #13131a;
    border: 1px solid #2a2a3a;
    border-left: 4px solid #7c6aff;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    font-family: 'Space Mono', monospace;
    font-size: 0.88rem;
    line-height: 1.8;
}
.ai-header {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.1rem;
    color: #7c6aff;
    margin-bottom: 0.8rem;
}
.tag { display:inline-block; padding:0.25rem 0.75rem; border-radius:20px; font-size:0.78rem; font-weight:700; margin:0.2rem; }
.tag-praise    { background:#1a3a2a; color:#6affb4; border:1px solid #6affb4; }
.tag-complaint { background:#3a1a1a; color:#ff6a6a; border:1px solid #ff6a6a; }
.tag-question  { background:#1a2a3a; color:#6ac4ff; border:1px solid #6ac4ff; }
.tag-request   { background:#2a1a3a; color:#c46aff; border:1px solid #c46aff; }
.tag-humor     { background:#3a3a1a; color:#fff06a; border:1px solid #fff06a; }
.tag-other     { background:#2a2a2a; color:#aaaaaa; border:1px solid #aaaaaa; }
.chat-user {
    background:#1e1e2e; border:1px solid #2a2a3a;
    border-radius:12px 12px 4px 12px;
    padding:0.8rem 1.1rem; margin:0.4rem 0;
    font-family:'Space Mono',monospace; font-size:0.85rem; text-align:right;
}
.chat-ai {
    background:#13131a; border:1px solid #7c6aff;
    border-radius:12px 12px 12px 4px;
    padding:0.8rem 1.1rem; margin:0.4rem 0;
    font-family:'Space Mono',monospace; font-size:0.85rem; line-height:1.6;
}
.section-title {
    font-family:'Syne',sans-serif; font-weight:800; font-size:1.4rem;
    margin:2rem 0 1rem; padding-bottom:0.5rem;
    border-bottom:1px solid #2a2a3a;
}
#MainMenu {visibility:hidden;} footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def delete_non_matching_csv_files(directory_path, video_id):
    if not video_id:
        return
    for file_name in os.listdir(directory_path):
        if not file_name.endswith('.csv'):
            continue
        if file_name == f'{video_id}.csv':
            continue
        try:
            os.remove(os.path.join(directory_path, file_name))
        except Exception:
            pass

def load_comments(csv_file, max_comments=120):
    comments = []
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                comments.append(row['Comment'])
                if len(comments) >= 1000:
                    break
    except Exception:
        pass
    return comments

def comments_to_text(comments, max_comments=25, max_chars=140):
    if not comments:
        return "No comments available."
    if len(comments) > max_comments:
        step = len(comments) / max_comments
        sampled = [comments[int(i * step)] for i in range(max_comments)]
    else:
        sampled = comments
    cleaned = []
    for c in sampled:
        txt = str(c).strip().replace("\n", " ")
        if txt:
            cleaned.append(f"- {txt[:max_chars]}")
    return "\n".join(cleaned)


# ── Groq AI functions ─────────────────────────────────────────────────────────
def call_ai(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400
    }
    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers)
        result = response.json()
        if "choices" not in result:
            error_msg = result.get("error", {}).get("message", str(result))
            return f"AI Error: {error_msg}"
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI Error: {str(e)}"

def get_ai_insights(comments):
    sample_text = comments_to_text(comments, max_comments=25, max_chars=140)
    prompt = f"""You are a YouTube audience analyst.
Analyze these viewer comments and provide:
1. SUMMARY: 3-4 plain English sentences covering what viewers loved, any complaints, and the overall mood (flowing prose, no bullet points).
2. THEMES: Select 2-5 themes from: praise, complaint, question, request, humor, nostalgia, excitement, disappointment.

COMMENTS:
{sample_text}

Reply in this exact format:
SUMMARY: <your 3-4 sentence summary>
THEMES: <theme1, theme2, theme3>"""
    resp = call_ai(prompt)
    if resp.startswith("AI Error:"):
        return resp, ["praise", "question"]
    summary = resp
    tags = ["praise", "question"]
    if "THEMES:" in resp:
        parts = resp.split("THEMES:")
        summary = parts[0].replace("SUMMARY:", "").strip()
        raw_tags = parts[1].strip()
        extracted = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
        if extracted:
            tags = extracted
    elif "SUMMARY:" in resp:
        summary = resp.replace("SUMMARY:", "").strip()
    return summary, tags

def get_ai_summary(comments):
    summary, _ = get_ai_insights(comments)
    return summary

def get_ai_tags(comments):
    _, tags = get_ai_insights(comments)
    return tags

def chat_with_comments(comments, history, question):
    history_text = ""
    for role, msg in history[-4:]:
        label = "User" if role == "user" else "Assistant"
        history_text += f"{label}: {msg}\n"
    sample_text = comments_to_text(comments, max_comments=20, max_chars=120)
    prompt = f"""Answer questions about YouTube comments.
Use ONLY the comments below. Be specific, 2-4 sentences.

COMMENTS:
{sample_text}

CONVERSATION:
{history_text}
User: {question}
Assistant:"""
    return call_ai(prompt)


# ── Session state ─────────────────────────────────────────────────────────────
for key, val in [("chat_history",[]),("ai_summary",None),("ai_tags",None),("current_video",None),("comments",[])]:
    if key not in st.session_state:
        st.session_state[key] = val


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🎯 YT Sentiment + AI")
st.sidebar.markdown("---")
youtube_link = st.sidebar.text_input("🔗 Paste YouTube Link here")
directory_path = os.getcwd()

# Landing page
if not youtube_link:
    st.markdown("""
    <div style='text-align:center; padding:5rem 2rem;'>
        <div style='font-size:5rem;'>🎯</div>
        <h1 style='font-size:2.8rem; font-weight:800;'>YouTube Sentiment + AI</h1>
        <p style='color:#7a7a9a; font-size:1rem; margin-top:1rem;'>
            Paste a YouTube link in the sidebar to get started.<br><br>
            ✦ VADER Sentiment &nbsp;|&nbsp; ✦ AI Summary &nbsp;|&nbsp; ✦ Chat with Comments
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── Main ──────────────────────────────────────────────────────────────────────
video_id = extract_video_id(youtube_link)
if not video_id:
    st.error("❌ Invalid YouTube link.")
    st.stop()

channel_id = get_channel_id(video_id)

if st.session_state.current_video != video_id:
    st.session_state.current_video = video_id
    st.session_state.ai_summary = None
    st.session_state.ai_tags = None
    st.session_state.chat_history = []

with st.spinner("⏳ Fetching comments..."):
    csv_file = save_video_comments_to_csv(video_id)
    delete_non_matching_csv_files(directory_path, video_id)
    st.session_state.comments = load_comments(csv_file)

st.sidebar.success(f"✅ {len(st.session_state.comments)} comments loaded!")
st.sidebar.download_button("⬇️ Download CSV", open(csv_file,'rb').read(), os.path.basename(csv_file), "text/csv")

# Channel Info
channel_info = get_channel_info(youtube, channel_id)
col1, col2 = st.columns([1, 3])
with col1:
    if channel_info.get('channel_logo_url'):
        st.image(channel_info['channel_logo_url'], width=180)
with col2:
    st.markdown(f"### {channel_info['channel_title']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("📹 Videos", channel_info['video_count'])
    c2.metric("📅 Created", channel_info['channel_created_date'][:10] if channel_info['channel_created_date'] else 'N/A')
    c3.metric("👥 Subscribers", channel_info['subscriber_count'])

st.markdown("---")

# Video Stats
st.markdown('<div class="section-title">📺 Video Stats</div>', unsafe_allow_html=True)
stats = get_video_stats(video_id)
v1, v2, v3 = st.columns(3)
v1.metric("👁️ Views", stats['viewCount'])
v2.metric("👍 Likes", stats['likeCount'])
v3.metric("💬 Comments", stats['commentCount'])
_, container, _ = st.columns([10, 80, 10])
container.video(data=youtube_link)

# Sentiment
st.markdown('<div class="section-title">📊 Sentiment Analysis (VADER)</div>', unsafe_allow_html=True)
st.caption("VADER scores each comment based on words — fast but basic.")
results = analyze_sentiment(csv_file)
s1, s2, s3 = st.columns(3)
s1.metric("😊 Positive", results['num_positive'])
s2.metric("😠 Negative", results['num_negative'])
s3.metric("😐 Neutral", results['num_neutral'])
bar_chart(csv_file)
plot_sentiment(csv_file)

# ── AI Features ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🤖 AI Insights (Groq AI)</div>', unsafe_allow_html=True)
st.caption("AI reads and understands the comments — like a human analyst.")

col_a, col_b = st.columns([5, 1])
with col_a:
    st.markdown("**🧠 AI Summary** — click Generate to analyze comments with AI")
with col_b:
    run_ai = st.button("✨ Generate")

if run_ai:
    with st.spinner("AI is reading comments... 🤖"):
        st.session_state.ai_summary, st.session_state.ai_tags = get_ai_insights(st.session_state.comments)

if st.session_state.ai_summary:
    st.markdown(f"""
    <div class="ai-card">
        <div class="ai-header">🧠 What viewers are saying</div>
        {st.session_state.ai_summary}
    </div>""", unsafe_allow_html=True)

    if st.session_state.ai_tags:
        tag_html = ""
        for tag in st.session_state.ai_tags:
            css = f"tag-{tag}" if tag in ['praise','complaint','question','request','humor'] else "tag-other"
            tag_html += f'<span class="tag {css}">#{tag}</span> '
        st.markdown(f"""
        <div class="ai-card">
            <div class="ai-header">🏷️ Detected Themes</div>
            {tag_html}
        </div>""", unsafe_allow_html=True)

# Chat
st.markdown('<div class="section-title">💬 Ask the Comments</div>', unsafe_allow_html=True)
st.caption("Ask AI anything about what viewers said.")

for role, content in st.session_state.chat_history:
    css_class = "chat-user" if role == "user" else "chat-ai"
    icon = "🧑" if role == "user" else "🤖"
    st.markdown(f'<div class="{css_class}">{icon} {content}</div>', unsafe_allow_html=True)

user_q = st.text_input("Your question:", placeholder="e.g. What do people complain about?", key="q_input")
col_ask, col_clear = st.columns([3, 1])
with col_ask:
    ask_clicked = st.button("Ask AI →")
with col_clear:
    if st.button("🗑️ Clear chat"):
        st.session_state.chat_history = []
        st.rerun()

if ask_clicked and user_q.strip():
    with st.spinner("AI is thinking... 💭"):
        answer = chat_with_comments(st.session_state.comments, st.session_state.chat_history, user_q)
    st.session_state.chat_history.append(("user", user_q))
    st.session_state.chat_history.append(("assistant", answer))
    st.rerun()

st.markdown("---")
st.subheader("📝 Channel Description")
st.write(channel_info.get('channel_description', ''))