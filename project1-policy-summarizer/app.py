from dotenv import load_dotenv
import os
import json
import re
from groq import Groq
import streamlit as st
import fitz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

load_dotenv()

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PolicyLens AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f1923 0%, #1a2d40 100%);
        color: #ffffff;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .hero {
        text-align: center;
        padding: 40px 20px 20px 20px;
    }
    .hero h1 {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4fc3f7, #00e5ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    .hero p {
        font-size: 1.1rem;
        color: #90caf9;
        margin-bottom: 30px;
    }
    .card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 24px;
        margin: 10px 0;
        backdrop-filter: blur(10px);
    }
    .summary-box {
        background: rgba(79, 195, 247, 0.08);
        border: 1px solid rgba(79, 195, 247, 0.3);
        border-radius: 16px;
        padding: 28px;
        margin: 20px 0;
        line-height: 1.8;
    }
    .badge {
        display: inline-block;
        background: rgba(79, 195, 247, 0.15);
        border: 1px solid rgba(79, 195, 247, 0.4);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.8rem;
        color: #4fc3f7;
        margin: 4px;
    }
    .stTextInput input, .stTextArea textarea {
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 10px !important;
        color: white !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #4fc3f7, #00b0ff) !important;
        border: none !important;
        border-radius: 12px !important;
        color: #0f1923 !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 14px !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(79, 195, 247, 0.4) !important;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 10px !important;
        color: white !important;
        font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #90caf9;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(79, 195, 247, 0.2) !important;
        color: #4fc3f7 !important;
    }
    hr { border-color: rgba(255,255,255,0.1) !important; }
    .metric-card {
        background: rgba(79, 195, 247, 0.08);
        border: 1px solid rgba(79, 195, 247, 0.2);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-number {
        font-size: 2rem;
        font-weight: 800;
        color: #4fc3f7;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #90caf9;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #4fc3f7;
        margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# GROQ CLIENT
# ─────────────────────────────────────────
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# FUNCTION 1 — Extract text from PDF
# ─────────────────────────────────────────
def extract_text_from_pdf(uploaded_file):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text


# ─────────────────────────────────────────
# FUNCTION 2 — Validate insurance document
# ─────────────────────────────────────────
def validate_policy_text(text):
    if len(text.strip()) < 100:
        return False, "The text is too short to be an insurance policy."

    validation_prompt = f"""
    You are an insurance document validator.
    Look at the following text and determine if it is a genuine insurance
    policy document or insurance-related content.

    Answer ONLY in this exact format:
    VALID: [YES or NO]
    REASON: [one line explanation]

    Text to validate:
    {text[:1000]}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a strict insurance document validator."},
            {"role": "user", "content": validation_prompt}
        ],
        temperature=0.1
    )

    result = response.choices[0].message.content.strip()

    if "VALID: YES" in result:
        return True, "Valid insurance document"
    else:
        reason = "Document does not appear to be an insurance policy"
        for line in result.split('\n'):
            if line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()
                break
        return False, reason


# ─────────────────────────────────────────
# FUNCTION 3 — Summarize policy
# ─────────────────────────────────────────
def summarize_policy(policy_text):
    prompt = f"""
    You are an expert insurance advisor. Analyze the following insurance policy
    and provide a clear, simple summary any common person can understand.

    Structure your response exactly like this:

    📋 POLICY OVERVIEW
    [2-3 lines about what this policy is]

    ✅ WHAT YOU ARE COVERED FOR
    [List key coverages in simple language]

    ❌ WHAT IS NOT COVERED
    [List exclusions in simple language]

    💰 COSTS YOU SHOULD KNOW
    [Premium, deductible, copayment explained simply]

    🏥 HOW TO MAKE A CLAIM
    [Simple step by step claim process]

    ⚠️ IMPORTANT DATES & LIMITS
    [Key limits and waiting periods]

    Keep language simple. Avoid jargon.
    Write as if explaining to someone who never read a policy before.

    POLICY TEXT:
    {policy_text}
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful insurance expert."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────
# FUNCTION 4 — Create PDF from summary
# ─────────────────────────────────────────
def create_summary_pdf(summary_text, title="Insurance Policy Summary"):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=60, leftMargin=60,
                            topMargin=60, bottomMargin=60)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Title'],
        fontSize=20, textColor=colors.HexColor('#1a3a5c'), spaceAfter=6)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'],
        fontSize=11, leading=18, spaceAfter=6)
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
        fontSize=8, textColor=colors.grey, alignment=1)

    story = []
    story.append(Paragraph(title, title_style))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor('#1a3a5c'), spaceAfter=12))

    for line in summary_text.split('\n'):
        if line.strip() == "":
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(line, normal_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.grey, spaceAfter=8))
    story.append(Paragraph(
        "Generated by PolicyLens AI | For reference only",
        footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────
# FUNCTION 5 — Send email via Gmail SMTP
# ─────────────────────────────────────────
def send_email(recipient_email, summary_text, pdf_bytes):
    sender_email = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Your Insurance Policy Summary — PolicyLens AI"

    body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;padding:20px;background:#f5f5f5;">
        <div style="max-width:600px;margin:0 auto;background:white;
                    border-radius:16px;padding:30px;">
            <h2 style="color:#1a3a5c;">Your Insurance Policy Summary</h2>
            <p>Hello,</p>
            <p>Your AI-generated insurance policy summary is attached as PDF.</p>
            <div style="background:#f0f7ff;border-radius:10px;
                        padding:20px;margin:20px 0;border-left:4px solid #4fc3f7;">
                <h3 style="color:#1a3a5c;margin-top:0;">Quick Preview:</h3>
                <pre style="font-size:13px;white-space:pre-wrap;color:#333;">
{summary_text[:600]}...
                </pre>
            </div>
            <p style="color:#888;font-size:12px;border-top:1px solid #eee;padding-top:15px;">
                Generated by PolicyLens AI | For reference only.
            </p>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment',
                          filename='policy_summary.pdf')
    msg.attach(attachment)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())


# ─────────────────────────────────────────
# FUNCTION 6 — Recommend alternatives
# ─────────────────────────────────────────
def recommend_alternatives(policy_text):
    prompt = f"""
    You are an expert Indian insurance advisor.

    Analyze this insurance policy and:

    STEP 1 — Extract:
    - Policy type (Health/Life/Vehicle/Home)
    - Current sum insured
    - Current annual premium
    - Policyholder age (if mentioned)
    - Key coverages

    STEP 2 — Recommend exactly 4 alternatives from:
    Star Health, HDFC Ergo, Niva Bupa, Care Health,
    Bajaj Allianz, ICICI Lombard, Tata AIG, Aditya Birla Health

    Respond in valid JSON only:
    {{
        "extracted": {{
            "policy_type": "",
            "current_sum_insured": "",
            "current_premium": "",
            "policyholder_age": "",
            "key_coverages": []
        }},
        "alternatives": [
            {{
                "insurer": "",
                "product": "",
                "estimated_premium": "",
                "sum_insured": "",
                "advantages": [],
                "weakness": "",
                "rating": 0.0,
                "claim_settlement_ratio": ""
            }}
        ]
    }}

    POLICY TEXT:
    {policy_text[:3000]}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Expert Indian insurance advisor. Respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ─────────────────────────────────────────
# HELPER — Build alternative cards HTML
# ─────────────────────────────────────────
def build_alt_cards(alternatives, show_why=False):
    all_cards = ""
    for alt in alternatives:
        rating = alt.get('rating', 0)
        stars = "⭐" * int(rating) + ("½" if rating % 1 >= 0.5 else "")
        adv_html = "".join([f"<li>✅ {a}</li>" for a in alt.get('advantages', [])])

        why_html = ""
        if show_why and alt.get('why_perfect'):
            why_html = (
                "<p style='color:#a5d6a7;margin:0 0 12px 0;"
                "font-size:0.9rem;background:rgba(165,214,167,0.1);"
                "padding:8px 12px;border-radius:8px;'>"
                "🎯 " + alt.get('why_perfect', '') + "</p>"
            )

        all_cards += (
            "<div style='background:rgba(79,195,247,0.06);"
            "border:1px solid rgba(79,195,247,0.25);"
            "border-radius:14px;padding:22px 26px;margin-bottom:16px;'>"

            "<div style='display:flex;justify-content:space-between;"
            "align-items:center;margin-bottom:8px;'>"
            "<h3 style='color:#4fc3f7;margin:0;'>"
            + alt.get('insurer', '') +
            "</h3><span style='color:#ffd54f;font-size:1.1rem;'>"
            + stars + " " + str(rating) + "/5</span></div>"

            "<p style='color:#90caf9;margin:0 0 10px 0;'>📦 "
            + alt.get('product', '') + "</p>"
            + why_html +

            "<div style='display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;'>"
            "<span style='background:rgba(0,229,255,0.1);"
            "border:1px solid rgba(0,229,255,0.3);"
            "border-radius:8px;padding:5px 12px;"
            "color:#00e5ff;font-weight:700;'>"
            "💰 " + alt.get('estimated_premium', '') + "/yr</span>"

            "<span style='background:rgba(0,229,255,0.1);"
            "border:1px solid rgba(0,229,255,0.3);"
            "border-radius:8px;padding:5px 12px;"
            "color:#00e5ff;font-weight:700;'>"
            "🛡️ " + alt.get('sum_insured', '') + "</span>"

            "<span style='background:rgba(0,229,255,0.1);"
            "border:1px solid rgba(0,229,255,0.3);"
            "border-radius:8px;padding:5px 12px;"
            "color:#00e5ff;font-weight:700;'>"
            "📊 " + alt.get('claim_settlement_ratio', '') + "</span>"
            "</div>"

            "<ul style='color:#e0f7fa;margin:0 0 10px 0;"
            "padding-left:18px;line-height:1.9;'>" + adv_html + "</ul>"

            "<p style='color:#ef9a9a;font-size:0.88rem;margin:0;'>"
            "⚠️ " + alt.get('weakness', '') + "</p>"
            "</div>"
        )
    return all_cards


# ═════════════════════════════════════════
# STREAMLIT UI
# ═════════════════════════════════════════

# ── HERO ──
st.markdown("""
<div class="hero">
    <h1>🛡️ PolicyLens AI</h1>
    <p>Upload any insurance policy — get a plain English summary in seconds</p>
    <span class="badge">⚡ Powered by LLaMA 3.3</span>
    <span class="badge">🔒 BFSI Grade</span>
    <span class="badge">📄 PDF Support</span>
    <span class="badge">💬 AI Chat Agent</span>
    <span class="badge">📧 Email Delivery</span>
</div>
""", unsafe_allow_html=True)

# ── STATS ──
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("""<div class="metric-card">
        <div class="metric-number">10s</div>
        <div class="metric-label">Average Analysis Time</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown("""<div class="metric-card">
        <div class="metric-number">6</div>
        <div class="metric-label">Key Sections Extracted</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown("""<div class="metric-card">
        <div class="metric-number">100%</div>
        <div class="metric-label">Free to Use</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── INPUT TABS ──
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-header">📂 Get Started</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📄 Upload PDF", "📝 Paste Text", "💬 Chat with AI Agent"])

policy_text = ""

# ── TAB 1: PDF Upload ──
with tab1:
    uploaded_file = st.file_uploader(
        "Drop your insurance policy PDF here",
        type="pdf",
        help="Supports health, life, vehicle, home insurance PDFs"
    )
    if uploaded_file is not None:
        with st.spinner("📖 Reading your PDF..."):
            policy_text = extract_text_from_pdf(uploaded_file)
        st.success(f"✅ PDF loaded — {len(policy_text):,} characters extracted")

# ── TAB 2: Paste Text ──
with tab2:
    pasted_text = st.text_area(
        "Paste your policy text here",
        height=250,
        placeholder="Copy and paste your insurance policy document text here..."
    )
    if pasted_text:
        policy_text = pasted_text

# ── TAB 3: Chat Agent ──
with tab3:
    st.markdown("""
    <p style="color:#90caf9;">
        Don't have a policy document? No problem. Chat with our AI agent —
        it'll ask the right questions and find the best policy for you.
    </p>
    """, unsafe_allow_html=True)

    if 'chat_messages' not in st.session_state:
        st.session_state['chat_messages'] = []
        st.session_state['chat_profile'] = {}
        st.session_state['chat_started'] = False
        st.session_state['profile_ready'] = False

    if not st.session_state['chat_started']:
        if st.button("🤖 Start Chat with AI Agent",
                     use_container_width=True, key="start_chat"):
            st.session_state['chat_started'] = True
            st.session_state['chat_messages'].append({
                "role": "assistant",
                "content": (
                    "Hello! 👋 I'm your AI insurance advisor.\n\n"
                    "I'll help you find the best insurance policy by asking "
                    "a few simple questions. Just answer honestly and I'll "
                    "find the best options for you.\n\n"
                    "Let's start! **What is your name?**"
                )
            })
            st.rerun()

    if st.session_state['chat_started']:

        for msg in st.session_state['chat_messages']:
            with st.chat_message(msg['role']):
                st.markdown(msg['content'])

        user_input = st.chat_input("Type your answer here...")

        if user_input:
            st.session_state['chat_messages'].append({
                "role": "user",
                "content": user_input
            })

            conversation_history = [
                {
                    "role": "system",
                    "content": """You are a friendly, professional Indian insurance advisor chatbot.

Your job is to collect information from users to recommend the best insurance policy.

Collect these details one or two questions at a time (never more than 2 at once):
1. Full name
2. Age
3. City in India
4. Occupation
5. Annual income range
6. Marital status and dependents
7. Pre-existing health conditions
8. Type of insurance needed (Health/Life/Vehicle/Home)
9. Coverage amount needed
10. Monthly/annual budget
11. Specific requirements (maternity, OPD, etc.)

Rules:
- Be conversational, warm and friendly
- Ask maximum 2 questions at a time
- Acknowledge previous answer before asking next
- Use simple English, avoid jargon
- Once you have all details, say exactly: "PROFILE_COMPLETE" on a new line,
  then provide JSON:
  {
    "name": "",
    "age": "",
    "city": "",
    "occupation": "",
    "income": "",
    "dependents": "",
    "health_conditions": "",
    "insurance_type": "",
    "coverage_needed": "",
    "budget": "",
    "special_requirements": ""
  }"""
                }
            ]

            for msg in st.session_state['chat_messages']:
                conversation_history.append({
                    "role": msg['role'],
                    "content": msg['content']
                })

            with st.spinner("Agent is typing..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=conversation_history,
                    temperature=0.7
                )

            ai_reply = response.choices[0].message.content

            if "PROFILE_COMPLETE" in ai_reply:
                parts = ai_reply.split("PROFILE_COMPLETE")
                display_message = parts[0].strip()
                json_match = re.search(r'\{.*\}', parts[1], re.DOTALL)
                if json_match:
                    try:
                        profile = json.loads(json_match.group())
                        st.session_state['chat_profile'] = profile
                        st.session_state['profile_ready'] = True
                    except:
                        pass

                st.session_state['chat_messages'].append({
                    "role": "assistant",
                    "content": (
                        (display_message + "\n\n" if display_message else "") +
                        "✅ **Perfect! I have all the information I need.**\n\n"
                        "Click **Find Best Policies** below to see your "
                        "personalized recommendations!"
                    )
                })
            else:
                st.session_state['chat_messages'].append({
                    "role": "assistant",
                    "content": ai_reply
                })

            st.rerun()

        if st.button("🔄 Start Over", key="reset_chat"):
            for key in ['chat_messages', 'chat_profile', 'chat_recommendations']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['chat_started'] = False
            st.session_state['profile_ready'] = False
            st.rerun()

        if st.session_state.get('profile_ready'):
            st.divider()
            if st.button("🏆 Find Best Policies For Me",
                         type="primary", use_container_width=True,
                         key="chat_recommend"):

                profile = st.session_state['chat_profile']
                chat_reco_prompt = f"""
                You are an expert Indian insurance advisor.

                Based on this customer profile, recommend exactly 4 best
                insurance products from: Star Health, HDFC Ergo, Niva Bupa,
                Care Health, Bajaj Allianz, ICICI Lombard, Tata AIG, Aditya Birla Health

                Customer Profile:
                - Name: {profile.get('name', 'Customer')}
                - Age: {profile.get('age', 'N/A')}
                - City: {profile.get('city', 'India')}
                - Occupation: {profile.get('occupation', 'N/A')}
                - Income: {profile.get('income', 'N/A')}
                - Dependents: {profile.get('dependents', 'N/A')}
                - Health Conditions: {profile.get('health_conditions', 'None')}
                - Insurance Type: {profile.get('insurance_type', 'Health')}
                - Coverage Needed: {profile.get('coverage_needed', 'N/A')}
                - Budget: {profile.get('budget', 'N/A')}
                - Special Requirements: {profile.get('special_requirements', 'None')}

                Respond in valid JSON only:
                {{
                    "customer_name": "",
                    "insurance_type": "",
                    "alternatives": [
                        {{
                            "insurer": "",
                            "product": "",
                            "why_perfect": "",
                            "estimated_premium": "",
                            "sum_insured": "",
                            "advantages": [],
                            "weakness": "",
                            "rating": 0.0,
                            "claim_settlement_ratio": ""
                        }}
                    ]
                }}
                """

                with st.spinner("🤖 Finding best policies for you..."):
                    reco_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": "Expert Indian insurance advisor. Respond with valid JSON only."},
                            {"role": "user", "content": chat_reco_prompt}
                        ],
                        temperature=0.2
                    )

                raw = reco_response.choices[0].message.content.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()

                try:
                    reco_data = json.loads(raw)
                    st.session_state['chat_recommendations'] = reco_data
                except:
                    st.error("Could not parse recommendations. Please try again.")

            if 'chat_recommendations' in st.session_state:
                reco = st.session_state['chat_recommendations']
                customer_name = reco.get('customer_name', 'You')
                alternatives = reco.get('alternatives', [])

                st.markdown(f"""
                <div style="background:rgba(79,195,247,0.08);
                            border:1px solid rgba(79,195,247,0.3);
                            border-radius:14px;padding:20px;margin:16px 0;">
                    <h3 style="color:#4fc3f7;margin:0;">
                        🎯 Personalized Recommendations for {customer_name}
                    </h3>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(
                    build_alt_cards(alternatives, show_why=True),
                    unsafe_allow_html=True
                )

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════
# DOCUMENT FLOW — Summarize button
# ══════════════════════════════════════════
if st.button("🔍 Analyze & Summarize Policy",
             type="primary", use_container_width=True):
    if policy_text == "":
        st.error("⚠️ Please upload a PDF or paste policy text first!")
    else:
        with st.spinner("🔎 Validating document..."):
            is_valid, validation_message = validate_policy_text(policy_text)

        if not is_valid:
            for key in ['summary', 'pdf_bytes']:
                if key in st.session_state:
                    del st.session_state[key]

            st.markdown("""
            <div style="background:rgba(255,82,82,0.1);
                        border:1px solid rgba(255,82,82,0.4);
                        border-radius:14px;padding:20px 24px;margin:16px 0;">
                <h4 style="color:#ff5252;margin:0 0 8px 0;">❌ Invalid Document</h4>
                <p style="color:#ffcdd2;margin:0 0 8px 0;">
                    This doesn't appear to be an insurance policy document.
                </p>
                <p style="color:#ef9a9a;font-size:0.9rem;margin:0;">
                    <b>Reason:</b> {reason}
                </p>
                <hr style="border-color:rgba(255,82,82,0.2);margin:12px 0;"/>
                <p style="color:#ef9a9a;font-size:0.85rem;margin:0;">
                    💡 Please upload a valid insurance policy PDF or paste
                    actual policy text.
                </p>
            </div>
            """.format(reason=validation_message), unsafe_allow_html=True)

        else:
            with st.spinner("🤖 AI is reading your policy... 10-15 seconds..."):
                summary = summarize_policy(policy_text)

            pdf_bytes = create_summary_pdf(summary)
            st.session_state['summary'] = summary
            st.session_state['pdf_bytes'] = pdf_bytes
            st.session_state['policy_text'] = policy_text
            st.toast("✅ Analysis complete!", icon="🎉")

# ── RESULTS ──
if 'summary' in st.session_state:

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">📊 Your Policy Summary</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="summary-box">{st.session_state["summary"]}</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">🚀 What would you like to do?</div>',
                unsafe_allow_html=True)

    act1, act2 = st.columns(2)

    with act1:
        st.markdown("**⬇️ Download Summary**")
        st.download_button(
            label="Download as PDF",
            data=st.session_state['pdf_bytes'],
            file_name="policy_summary.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with act2:
        st.markdown("**📧 Email Summary**")
        recipient_email = st.text_input(
            "Email",
            placeholder="example@gmail.com",
            label_visibility="collapsed"
        )
        if st.button("Send to Email", use_container_width=True):
            if not recipient_email:
                st.error("Enter an email address!")
            elif "@" not in recipient_email:
                st.error("Enter a valid email!")
            else:
                with st.spinner("Sending..."):
                    try:
                        send_email(
                            recipient_email,
                            st.session_state['summary'],
                            st.session_state['pdf_bytes']
                        )
                        st.toast("✅ Email sent!", icon="📧")
                    except Exception as e:
                        st.error(f"❌ {str(e)}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── ALTERNATIVES ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-header">🏆 Better Alternatives in the Market</div>
    <p style="color:#90caf9;margin-bottom:16px;">
        Based on your current policy, our AI found better options
        available in the Indian market right now.
    </p>
    """, unsafe_allow_html=True)

    if st.button("🔍 Find Better Alternatives", use_container_width=True):
        with st.spinner("🤖 Analyzing Indian insurance market..."):
            try:
                reco_data = recommend_alternatives(
                    st.session_state.get('policy_text', '')
                )
                st.session_state['recommendations'] = reco_data
            except Exception as e:
                st.error(f"❌ Could not fetch recommendations: {str(e)}")

    if 'recommendations' in st.session_state:
        reco = st.session_state['recommendations']
        extracted = reco.get('extracted', {})
        alternatives = reco.get('alternatives', [])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**📋 Your Current Policy Details:**")

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-number" style="font-size:1.2rem;">
                    {extracted.get('policy_type', 'N/A')}
                </div>
                <div class="metric-label">Policy Type</div>
            </div>""", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-number" style="font-size:1.2rem;">
                    {extracted.get('current_sum_insured', 'N/A')}
                </div>
                <div class="metric-label">Sum Insured</div>
            </div>""", unsafe_allow_html=True)
        with sc3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-number" style="font-size:1.2rem;">
                    {extracted.get('current_premium', 'N/A')}
                </div>
                <div class="metric-label">Current Premium</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🏆 Recommended Alternatives:**")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(build_alt_cards(alternatives), unsafe_allow_html=True)

        # ── GENERATE QUOTE ──
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**📝 Want a detailed quote?**")

        selected_insurer = st.selectbox(
            "Select insurer",
            [alt.get('insurer', '') for alt in alternatives],
            label_visibility="collapsed"
        )

        if st.button("📄 Generate Detailed Quote", use_container_width=True):
            with st.spinner(f"Generating quote from {selected_insurer}..."):
                quote_prompt = f"""
                Generate a detailed insurance quote for:
                - Insurer: {selected_insurer}
                - Policy Type: {extracted.get('policy_type', 'Health')}
                - Sum Insured: {extracted.get('current_sum_insured', '5 Lakhs')}
                - Age: {extracted.get('policyholder_age', '35 years')}

                Include:
                - Base premium breakdown
                - Add-on covers with costs
                - Applicable discounts
                - Final premium calculation
                - Payment options (monthly/quarterly/annual)
                - Key policy terms
                - How to apply

                Use realistic Indian market pricing in Rs.
                Make it look like an actual insurance quote document.
                """

                quote_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Expert Indian insurance agent generating detailed quotes."},
                        {"role": "user", "content": quote_prompt}
                    ]
                )

                st.session_state['quote_text'] = quote_response.choices[0].message.content
                st.session_state['quote_insurer'] = selected_insurer

        if 'quote_text' in st.session_state:
            st.markdown(f"""
            <div style="background:rgba(255,213,79,0.06);
                        border:1px solid rgba(255,213,79,0.3);
                        border-radius:14px;padding:24px;margin-top:16px;">
                <h3 style="color:#ffd54f;">
                    📄 Quote from {st.session_state['quote_insurer']}
                </h3>
                <div style="color:#fff3e0;line-height:1.8;white-space:pre-wrap;">
{st.session_state['quote_text']}
                </div>
            </div>
            """, unsafe_allow_html=True)

            quote_pdf = create_summary_pdf(
                st.session_state['quote_text'],
                f"Quote — {st.session_state['quote_insurer']}"
            )
            st.download_button(
                label=f"⬇️ Download {st.session_state['quote_insurer']} Quote as PDF",
                data=quote_pdf,
                file_name=f"quote_{st.session_state['quote_insurer'].lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    st.markdown('</div>', unsafe_allow_html=True)

# ── FOOTER ──
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;color:rgba(255,255,255,0.3);font-size:0.8rem;">
    PolicyLens AI — Built with Python, Groq, LLaMA 3.3 & Streamlit<br>
    For reference only. Consult your insurer for official policy details.
</div>
""", unsafe_allow_html=True)
