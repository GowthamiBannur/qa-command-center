import streamlit as st
from supabase import create_client
from groq import Groq
import json, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="QA Command Center", page_icon="🧪", layout="wide", initial_sidebar_state="expanded")

# ── Global CSS theme ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif !important;
}

/* Background */
.stApp {
    background: #050d1a !important;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% 10%, rgba(0,200,180,0.07) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(0,120,255,0.06) 0%, transparent 60%),
        repeating-linear-gradient(
            0deg,
            transparent,
            transparent 39px,
            rgba(0,200,180,0.03) 40px
        ),
        repeating-linear-gradient(
            90deg,
            transparent,
            transparent 39px,
            rgba(0,200,180,0.03) 40px
        ) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #040c17 !important;
    border-right: 1px solid rgba(0,200,180,0.12) !important;
}
section[data-testid="stSidebar"] * {
    font-family: 'Outfit', sans-serif !important;
    color: #a8c4c0 !important;
}

/* Sidebar title */
section[data-testid="stSidebar"] h1 {
    color: #00c8b4 !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
}

/* Nav radio */
div[role="radiogroup"] label {
    border-radius: 8px !important;
    padding: 6px 12px !important;
    transition: all 0.2s !important;
}
div[role="radiogroup"] label:hover {
    background: rgba(0,200,180,0.08) !important;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: rgba(0,200,180,0.05) !important;
    border: 1px solid rgba(0,200,180,0.15) !important;
    border-radius: 12px !important;
    padding: 16px !important;
}
[data-testid="metric-container"] label {
    color: #6b8f8b !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #00c8b4 !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
}

/* Expanders */
details {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(0,200,180,0.12) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}
details summary {
    color: #cce8e4 !important;
    font-weight: 500 !important;
    padding: 4px !important;
}

/* Inputs */
input, textarea, select, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
    background: rgba(0,200,180,0.04) !important;
    border: 1px solid rgba(0,200,180,0.18) !important;
    border-radius: 8px !important;
    color: #e2f0ee !important;
    font-family: 'Outfit', sans-serif !important;
}
input:focus, textarea:focus {
    border-color: #00c8b4 !important;
    box-shadow: 0 0 0 2px rgba(0,200,180,0.15) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00c8b4, #0098a8) !important;
    color: #050d1a !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Outfit', sans-serif !important;
    transition: all 0.2s !important;
    letter-spacing: 0.02em !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(0,200,180,0.3) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid rgba(0,200,180,0.3) !important;
    color: #00c8b4 !important;
}

/* Tabs */
[data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(0,200,180,0.15) !important;
    gap: 4px !important;
}
[data-baseweb="tab"] {
    background: transparent !important;
    color: #6b8f8b !important;
    border-radius: 8px 8px 0 0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: #00c8b4 !important;
    border-bottom: 2px solid #00c8b4 !important;
    background: rgba(0,200,180,0.06) !important;
}

/* Selectbox */
[data-baseweb="select"] > div {
    background: rgba(0,200,180,0.04) !important;
    border: 1px solid rgba(0,200,180,0.18) !important;
    border-radius: 8px !important;
    color: #e2f0ee !important;
}

/* Titles */
h1, h2, h3 {
    color: #e2f0ee !important;
    font-family: 'Outfit', sans-serif !important;
}
h1 { font-weight: 700 !important; letter-spacing: -0.02em !important; }

/* Divider */
hr { border-color: rgba(0,200,180,0.1) !important; }

/* Success / info / warning */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-family: 'Outfit', sans-serif !important;
}

/* Progress bar */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #00c8b4, #0098a8) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #040c17; }
::-webkit-scrollbar-thumb { background: rgba(0,200,180,0.3); border-radius: 3px; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden !important; }

/* Sidebar width */
section[data-testid="stSidebar"] > div:first-child {
    width: 300px !important;
    padding-top: 1rem !important;
}

/* Auth modal overlay */
.auth-overlay {
    position: fixed; inset: 0;
    background: rgba(5,13,26,0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 9999;
    display: flex; align-items: center; justify-content: center;
}
.auth-card {
    background: linear-gradient(145deg, #0a1f2e, #071524);
    border: 1px solid rgba(0,200,180,0.25);
    border-radius: 20px;
    padding: 40px 44px;
    width: 420px;
    box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,200,180,0.1);
}

/* Notification page */
.notif-item {
    background: rgba(0,200,180,0.04);
    border: 1px solid rgba(0,200,180,0.1);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.notif-item.unread {
    border-left: 3px solid #00c8b4;
    background: rgba(0,200,180,0.07);
}
.notif-dot {
    display: inline-block;
    width: 8px; height: 8px;
    background: #00c8b4;
    border-radius: 50%;
    margin-right: 8px;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_clients():
    sb   = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    return sb, groq

supabase, groq_client = init_clients()

PRIORITY_ICON = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🟢"}
SEVERITY_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
STATUS_ICON   = {"Not Run": "⬜", "Pass": "✅", "Fail": "❌", "Blocked": "🚫",
                 "Open": "🔓", "In Progress": "🔄", "Resolved": "✅"}

# ═══════════════════════════════════════════════════════════════
# HELPERS — AI
# ═══════════════════════════════════════════════════════════════

def extract_json(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{"); end = text.rfind("}") + 1
    if start == -1 or end == 0:
        st.warning("⚠️ Model didn't return JSON."); st.code(text[:600]); return None
    raw = text[start:end]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    def fix_pipes(s):
        def rep(m):
            lines = [l.strip() for l in m.group(2).split("\n") if l.strip()]
            return f'"{m.group(1)}": "{chr(92)+"n".join(lines)}"'
        return re.sub(r'"(\w+)"\s*:\s*\|\s*\n((?:[ \t]+.+\n?)*)', rep, s)
    raw = fix_pipes(raw)
    fixed = re.sub(r'(?<!\\)\n', r'\\n', raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ JSON parse error: {e} — try again."); st.code(raw[:800]); return None


def call_groq(prompt: str, retries: int = 3) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile", max_tokens=4096, temperature=0.3,
                messages=[
                    {"role": "system", "content":
                        "You are a Senior QA Engineer. Respond with ONLY a single raw valid JSON object. "
                        "No markdown, no code fences, no commentary. Never truncate."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = resp.choices[0].message.content or ""
            if content.strip(): return content
            st.toast(f"Empty AI response, retrying ({attempt}/{retries})…")
        except Exception as e:
            st.error(f"Groq error (attempt {attempt}): {e}")
    st.error("AI failed after all retries."); return None

# ═══════════════════════════════════════════════════════════════
# HELPERS — EMAIL
# ═══════════════════════════════════════════════════════════════

def send_email(to_email: str, subject: str, body_html: str, cc_email: str = "") -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = st.secrets["GMAIL_ADDRESS"]
        msg["To"]      = to_email
        if cc_email.strip(): msg["Cc"] = cc_email.strip()
        msg.attach(MIMEText(body_html, "html"))
        recipients = [to_email] + ([cc_email.strip()] if cc_email.strip() else [])
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(st.secrets["GMAIL_ADDRESS"], st.secrets["GMAIL_APP_PASSWORD"])
            srv.sendmail(st.secrets["GMAIL_ADDRESS"], recipients, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Email failed: {e}"); return False


def bug_email_html(tc: dict, bug: dict, reporter_name: str) -> str:
    sev_color = {"Critical":"#dc2626","High":"#ea580c","Medium":"#ca8a04","Low":"#16a34a"}.get(bug.get("severity",""),"#6b7280")
    steps_html = (bug.get("steps") or "—").replace("\\n", "<br>")
    return f"""
<div style="font-family:sans-serif;max-width:600px;margin:auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
  <div style="background:linear-gradient(135deg,#00c8b4,#0098a8);padding:24px">
    <h2 style="color:#050d1a;margin:0;font-weight:700">🐛 Bug Assigned to You</h2>
    <p style="color:#033540;margin:4px 0 0;font-size:13px">QA Command Center</p>
  </div>
  <div style="padding:24px;background:#f8fafc">
    <p>Hi <strong>{bug.get('assigned_to','Developer')}</strong>,</p>
    <p><strong>{reporter_name}</strong> has assigned a bug to you.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;width:140px;font-size:13px">Summary</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px">{bug.get('summary','')}</td></tr>
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px">Severity</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb">
            <span style="background:{sev_color};color:#fff;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:600">{bug.get('severity','')}</span></td></tr>
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px">Feature</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px">{tc.get('feature_name','—')}</td></tr>
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px">Steps</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px">{steps_html}</td></tr>
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px">Expected</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px">{bug.get('expected_result','—')}</td></tr>
      <tr><td style="padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px">Actual</td>
          <td style="padding:10px 14px;font-size:13px">{bug.get('actual_result','—')}</td></tr>
      {"<tr><td style='padding:10px 14px;background:#f1f5f9;font-weight:600;font-size:13px'>Evidence</td><td style='padding:10px 14px'><a href='" + bug.get('evidence_url','') + "' style='color:#00c8b4'>View Screenshot</a></td></tr>" if bug.get('evidence_url') else ""}
    </table>
    <p style="color:#6b7280;font-size:12px;margin-top:20px">Please investigate and update the bug status in QA Command Center.</p>
  </div>
</div>"""

# ═══════════════════════════════════════════════════════════════
# HELPERS — NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

def push_notification(actor_name: str, action: str, entity_type: str = "",
                      entity_id: str = None, project_id: str = None, actor_email: str = ""):
    try:
        supabase.table("notifications").insert({
            "actor_name": actor_name, "actor_email": actor_email,
            "action": action, "entity_type": entity_type,
            "entity_id": entity_id, "project_id": project_id,
        }).execute()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# HELPERS — MISC
# ═══════════════════════════════════════════════════════════════

def validate(**fields) -> list[str]:
    return [k for k, v in fields.items() if not str(v or "").strip()]

@st.cache_data(ttl=30)
def get_projects():
    return supabase.table("projects").select("*").order("created_at", desc=True).execute().data or []

def get_project_id(projects, name):
    return next((p["id"] for p in projects if p["name"] == name), None)

def require_project():
    if not st.session_state.get("project_id"):
        st.markdown("""
        <div style="background:rgba(0,200,180,0.07);border:1px solid rgba(0,200,180,0.25);
             border-radius:12px;padding:24px 28px;margin-top:20px;text-align:center">
          <div style="font-size:36px;margin-bottom:12px">👈</div>
          <div style="color:#00c8b4;font-size:16px;font-weight:600;font-family:Outfit,sans-serif;margin-bottom:6px">
            Select a Project from the Sidebar
          </div>
          <div style="color:#4a7a74;font-size:13px;font-family:Outfit,sans-serif">
            Use the <b style="color:#00c8b4">PROJECT</b> dropdown in the left sidebar,
            or click <b style="color:#00c8b4">+ New Project</b> to create one.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

# ═══════════════════════════════════════════════════════════════
# AUTH — NATIVE STREAMLIT DIALOG (works reliably on Streamlit Cloud)
# ═══════════════════════════════════════════════════════════════

if "user" not in st.session_state:
    st.session_state["user"] = None
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "login"   # login | request | pending

user = st.session_state["user"]

@st.dialog(" ")
def auth_dialog():
    mode = st.session_state["auth_mode"]

    # ── Header ──────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:8px 0 20px">
      <div style="font-size:44px">🧪</div>
      <h2 style="color:#e2f0ee;font-family:Outfit,sans-serif;font-weight:700;
          margin:6px 0 4px;font-size:22px;letter-spacing:-0.01em">QA Command Center</h2>
      <p style="color:#4a7a74;font-size:13px;margin:0;font-family:Outfit,sans-serif">
        AI-powered QA workspace
      </p>
    </div>
    """, unsafe_allow_html=True)

    if mode == "pending":
        st.markdown("""
        <div style="text-align:center;padding:12px 0">
          <div style="font-size:48px;margin-bottom:12px">⏳</div>
          <h3 style="color:#00c8b4;font-family:Outfit,sans-serif;margin:0 0 10px">Access Pending</h3>
          <p style="color:#7ab8b2;font-size:14px;line-height:1.7;margin:0 0 16px;font-family:Outfit,sans-serif">
            Your request has been submitted.<br>
            The admin will review and approve it shortly.<br>
            You'll receive an email once approved.
          </p>
        </div>
        """, unsafe_allow_html=True)
        st.info("📧 Check your inbox for approval notification.")
        if st.button("← Back to Login", use_container_width=True):
            st.session_state["auth_mode"] = "login"
            st.rerun()
        return

    # ── Tab toggle ───────────────────────────────────────────────
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        login_active = "background:rgba(0,200,180,0.15);border:1px solid rgba(0,200,180,0.4);color:#00c8b4;" if mode=="login" else "background:transparent;border:1px solid rgba(255,255,255,0.08);color:#4a7a74;"
        st.markdown(f'<div style="{login_active}text-align:center;padding:8px 0;border-radius:8px;font-family:Outfit,sans-serif;font-weight:600;font-size:14px">🔐 Login</div>', unsafe_allow_html=True)
    with col_t2:
        req_active = "background:rgba(0,200,180,0.15);border:1px solid rgba(0,200,180,0.4);color:#00c8b4;" if mode=="request" else "background:transparent;border:1px solid rgba(255,255,255,0.08);color:#4a7a74;"
        st.markdown(f'<div style="{req_active}text-align:center;padding:8px 0;border-radius:8px;font-family:Outfit,sans-serif;font-weight:600;font-size:14px">✋ Request Access</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if mode == "login":
        st.markdown('<p style="color:#7ab8b2;font-size:13px;margin:0 0 6px;font-family:Outfit,sans-serif">Work email</p>', unsafe_allow_html=True)
        login_email = st.text_input("email", placeholder="you@company.com",
                                     key="dlg_login_email", label_visibility="collapsed")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔐 Login", type="primary", key="dlg_btn_login", use_container_width=True):
                if not login_email.strip():
                    st.error("Enter your email.")
                else:
                    result = supabase.table("users").select("*")                                  .eq("email", login_email.strip().lower()).execute().data
                    if not result:
                        st.error("No account. Request access →")
                    elif result[0]["status"] == "pending":
                        st.session_state["auth_mode"] = "pending"
                        st.rerun()
                    elif result[0]["status"] == "rejected":
                        st.error("Access rejected. Contact admin.")
                    else:
                        st.session_state["user"] = result[0]
                        st.rerun()
        with col_b:
            if st.button("✋ Request Access", key="dlg_go_req", use_container_width=True):
                st.session_state["auth_mode"] = "request"
                st.rerun()

    else:  # request
        st.markdown('<p style="color:#7ab8b2;font-size:13px;margin:0 0 6px;font-family:Outfit,sans-serif">Full name</p>', unsafe_allow_html=True)
        req_name  = st.text_input("name", placeholder="Priya Sharma",
                                   key="dlg_req_name", label_visibility="collapsed")
        st.markdown('<p style="color:#7ab8b2;font-size:13px;margin:4px 0 6px;font-family:Outfit,sans-serif">Work email</p>', unsafe_allow_html=True)
        req_email = st.text_input("reqemail", placeholder="priya@company.com",
                                   key="dlg_req_email", label_visibility="collapsed")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✋ Submit Request", type="primary", key="dlg_btn_req", use_container_width=True):
                missing = validate(name=req_name, email=req_email)
                if missing:
                    st.error(f"Fill in: {', '.join(missing)}")
                else:
                    email_clean = req_email.strip().lower()
                    existing = supabase.table("users").select("id,status").eq("email", email_clean).execute().data
                    if existing:
                        s = existing[0]["status"]
                        if s == "approved":
                            st.info("You already have access! Use Login tab.")
                        elif s == "pending":
                            st.session_state["auth_mode"] = "pending"; st.rerun()
                        else:
                            st.error("Previously rejected. Contact admin.")
                    else:
                        supabase.table("users").insert({
                            "name": req_name.strip(), "email": email_clean,
                            "role": "member", "status": "pending"
                        }).execute()
                        push_notification(req_name.strip(),
                            "requested access to QA Command Center", "user",
                            actor_email=email_clean)
                        try:
                            send_email(
                                to_email=st.secrets["GMAIL_ADDRESS"],
                                subject=f"[QA Center] Access request from {req_name.strip()}",
                                body_html=f"""<div style="font-family:sans-serif;max-width:500px;padding:24px">
  <h3 style="color:#00c8b4">New Access Request</h3>
  <p><b>Name:</b> {req_name.strip()}<br><b>Email:</b> {email_clean}</p>
  <p>Log in as admin to approve or reject.</p>
</div>"""
                            )
                        except Exception:
                            pass
                        st.session_state["auth_mode"] = "pending"
                        st.rerun()
        with col_b:
            if st.button("← Back to Login", key="dlg_back_login", use_container_width=True):
                st.session_state["auth_mode"] = "login"
                st.rerun()


if not user:
    # Show the blurred background page content behind the dialog
    st.markdown("""
    <div style="text-align:center;padding:180px 20px 0;opacity:0.04;pointer-events:none;user-select:none">
      <div style="font-size:100px">🧪</div>
      <div style="color:#00c8b4;font-size:28px;font-family:Outfit,sans-serif;font-weight:700;
           letter-spacing:0.15em;margin-top:16px">QA COMMAND CENTER</div>
      <div style="color:#00c8b4;font-size:13px;letter-spacing:0.3em;margin-top:8px;opacity:0.5">
        AI · AUDIT · TESTCASES · BUGS · DASHBOARD
      </div>
    </div>
    """, unsafe_allow_html=True)
    auth_dialog()
    st.stop()

# ═══════════════════════════════════════════════════════════════
# LOGGED IN — MAIN APP
# ═══════════════════════════════════════════════════════════════


is_admin = user.get("role") == "admin"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

# ── Sidebar header ───────────────────────────────────────────
st.sidebar.title("🧪 QA Command Center")
st.sidebar.caption("🛡 Admin" if is_admin else "👤 Member")
st.sidebar.divider()

# ── Navigation ────────────────────────────────────────────────
notifs_all   = supabase.table("notifications").select("id,is_read") \
                   .order("created_at", desc=True).limit(60).execute().data or []
unread_count = sum(1 for n in notifs_all if not n.get("is_read"))
bell_label   = f"🔔 Notifications ({unread_count} new)" if unread_count else "🔔 Notifications"

nav_options = ["🚀 Generate & Audit", "📁 Testcases", "🐛 Bug Center", "📊 Dashboard"]
if is_admin:
    nav_options.append("👥 Team Access")
nav_options.append(bell_label)

menu = st.sidebar.radio("Navigate", nav_options, label_visibility="collapsed")
st.sidebar.divider()

# ── Project picker ────────────────────────────────────────────
projects      = get_projects()
project_names = [p["name"] for p in projects]
_auto         = st.session_state.pop("_auto_select_proj", None)
_proj_list    = project_names if project_names else ["— No projects yet —"]
_default_idx  = _proj_list.index(_auto) if (_auto and _auto in _proj_list) else 0

st.sidebar.markdown("**PROJECT**")
sel_proj   = st.sidebar.selectbox("Project", _proj_list, index=_default_idx, label_visibility="collapsed")
project_id = get_project_id(projects, sel_proj)
st.session_state["project_id"] = project_id

if project_id:
    st.sidebar.success(f"📂 {sel_proj}")

# ── New Project ───────────────────────────────────────────────
with st.sidebar.expander("➕ New Project"):
    new_proj = st.text_input("Project name", key="new_proj_input",
                              placeholder="e.g. Search Revamp v2",
                              label_visibility="collapsed")
    if st.button("Create", key="btn_new_proj", use_container_width=True, type="primary"):
        name = new_proj.strip()
        if not name:
            st.error("Name required.")
        elif name in project_names:
            st.warning(f'"{name}" already exists.')
        else:
            try:
                supabase.table("projects").insert({"name": name, "created_by": user["id"]}).execute()
                push_notification(user["name"], f"created project **{name}**", "project",
                                  actor_email=user.get("email",""))
                st.cache_data.clear()
                st.session_state["_auto_select_proj"] = name
                st.toast(f'Project "{name}" created!', icon="🎉")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

st.sidebar.divider()
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state["user"] = None
    st.session_state["auth_mode"] = "login"
    st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE — NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

is_notif_page = bell_label in menu

if is_notif_page:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
      <span style="font-size:28px">🔔</span>
      <h1 style="margin:0;font-family:Outfit,sans-serif;font-weight:700;color:#e2f0ee;font-size:28px">Notifications</h1>
    </div>
    """, unsafe_allow_html=True)

    notifs = supabase.table("notifications").select("*") \
                 .order("created_at", desc=True).limit(60).execute().data or []
    unread = [n for n in notifs if not n.get("is_read")]

    col_a, col_b, col_c = st.columns([2,1,1])
    col_a.markdown(f'<p style="color:#4a7a74;font-family:Outfit,sans-serif;font-size:14px;margin:8px 0">{len(notifs)} total  ·  <span style="color:#00c8b4">{len(unread)} unread</span></p>', unsafe_allow_html=True)
    with col_b:
        if unread and st.button("✓ Mark all read", use_container_width=True):
            supabase.table("notifications").update({"is_read": True}).eq("is_read", False).execute()
            st.rerun()
    with col_c:
        if notifs and st.button("🗑 Clear all", use_container_width=True):
            supabase.table("notifications").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            st.rerun()

    st.divider()

    if not notifs:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#3a6660;font-family:Outfit,sans-serif">
          <div style="font-size:48px;margin-bottom:16px;opacity:0.4">🔔</div>
          <p style="font-size:16px;margin:0">No notifications yet</p>
          <p style="font-size:13px;margin:4px 0 0;opacity:0.6">Actions by your team will show up here</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Group by entity type
        entity_icons = {"audit":"📋","testcase":"🧪","bug":"🐛","project":"📁","user":"👤","":"🔔"}
        for n in notifs:
            is_unread = not n.get("is_read")
            icon      = entity_icons.get(n.get("entity_type",""),"🔔")
            ts        = n.get("created_at","")[:16].replace("T"," ")
            dot       = '<span style="display:inline-block;width:8px;height:8px;background:#00c8b4;border-radius:50%;margin-right:10px;vertical-align:middle"></span>' if is_unread else '<span style="display:inline-block;width:8px;height:8px;margin-right:10px"></span>'
            border_style = "border-left:3px solid #00c8b4;" if is_unread else "border-left:3px solid transparent;"
            bg_style     = "background:rgba(0,200,180,0.07);" if is_unread else "background:rgba(255,255,255,0.02);"

            st.markdown(f"""
            <div style="{bg_style}{border_style}border:1px solid rgba(0,200,180,0.1);
                 border-radius:10px;padding:14px 18px;margin-bottom:8px;
                 transition:all 0.2s">
              <div style="display:flex;align-items:flex-start;gap:12px">
                <span style="font-size:20px;line-height:1.4">{icon}</span>
                <div style="flex:1">
                  {dot}<strong style="color:#cce8e4;font-family:Outfit,sans-serif;font-size:14px">{n['actor_name']}</strong>
                  <span style="color:#7ab8b2;font-family:Outfit,sans-serif;font-size:14px"> {n['action']}</span>
                  <div style="color:#3a6660;font-size:11px;font-family:JetBrains Mono,monospace;
                       margin-top:5px;letter-spacing:0.04em">{ts}</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if is_unread:
                supabase.table("notifications").update({"is_read": True}).eq("id", n["id"]).execute()

# ═══════════════════════════════════════════════════════════════
# PAGE — TEAM ACCESS (admin only)
# ═══════════════════════════════════════════════════════════════

elif menu == "👥 Team Access" and is_admin:
    st.title("👥 Team Access")

    tab_pending, tab_all = st.tabs(["⏳ Pending Requests", "👥 All Members"])

    with tab_pending:
        pending = supabase.table("users").select("*").eq("status","pending").order("created_at").execute().data or []
        if not pending:
            st.success("✅ No pending requests.")
        else:
            st.info(f"{len(pending)} request(s) waiting.")
            for u in pending:
                with st.expander(f"✋ {u['name']}  ·  {u['email']}  ·  {u['created_at'][:10]}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Approve", key=f"apr_{u['id']}", type="primary"):
                            supabase.table("users").update({"status":"approved"}).eq("id",u["id"]).execute()
                            push_notification(user["name"], f"approved access for **{u['name']}**", "user")
                            send_email(u["email"],
                                "✅ QA Command Center — Access Approved!",
                                f"""<div style="font-family:sans-serif;max-width:500px">
                                <h3 style="color:#00c8b4">🎉 Access Approved!</h3>
                                <p>Hi <b>{u['name']}</b>, your request has been approved.</p>
                                <p>Log in with: <b>{u['email']}</b></p></div>""")
                            st.success(f"Approved! Email sent to {u['email']}.")
                            st.rerun()
                    with c2:
                        if st.button("❌ Reject", key=f"rej_{u['id']}"):
                            supabase.table("users").update({"status":"rejected"}).eq("id",u["id"]).execute()
                            send_email(u["email"], "QA Command Center — Access Update",
                                f"""<div style="font-family:sans-serif;max-width:500px">
                                <p>Hi <b>{u['name']}</b>, your access request was not approved.</p></div>""")
                            st.rerun()

    with tab_all:
        all_users = supabase.table("users").select("*").order("created_at").execute().data or []
        for u in all_users:
            s_icon = {"approved":"✅","pending":"⏳","rejected":"❌"}.get(u["status"],"❓")
            r_icon = "🛡" if u["role"]=="admin" else "👤"
            with st.expander(f"{s_icon} {r_icon} {u['name']}  ·  {u['email']}"):
                st.write(f"**Status:** {u['status']}  |  **Role:** {u['role']}  |  **Joined:** {u['created_at'][:10]}")
                if u["id"] != user["id"]:
                    mc1, mc2, mc3 = st.columns(3)
                    new_role = "member" if u["role"]=="admin" else "admin"
                    with mc1:
                        if st.button(f"Make {new_role}", key=f"role_{u['id']}"):
                            supabase.table("users").update({"role":new_role}).eq("id",u["id"]).execute()
                            st.rerun()
                    with mc2:
                        if u["status"]=="approved" and st.button("Revoke", key=f"rev_{u['id']}"):
                            supabase.table("users").update({"status":"rejected"}).eq("id",u["id"]).execute()
                            st.rerun()
                    with mc3:
                        if st.button("🗑 Remove", key=f"rem_{u['id']}"):
                            supabase.table("users").delete().eq("id",u["id"]).execute()
                            st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — GENERATE & AUDIT
# ═══════════════════════════════════════════════════════════════

elif menu == "🚀 Generate & Audit":
    st.title("🚀 Generate Audit + Testcases")
    require_project()

    tab_gen, tab_history = st.tabs(["📝 New Audit", "🗂 Audit History"])

    with tab_gen:
        feature_name = st.text_input("Feature Name *", placeholder="e.g. Search Revamp")
        prd_text     = st.text_area("Paste PRD *", height=260, placeholder="Paste full PRD here…")

        if st.button("🚀 Generate Audit + Testcases", type="primary"):
            missing = validate(feature=feature_name, prd=prd_text)
            if missing: st.error(f"Fill in: {', '.join(missing)}"); st.stop()

            with st.spinner("Step 1/2 — Generating QA Audit…"):
                audit_prompt = f"""
You are a Senior QA Engineer with 10+ years experience.
Analyse this PRD and return ONLY a raw JSON object (no fences, no prose).
All string values must be single-line. Use \\n for line breaks. Do NOT use YAML pipe syntax.
Feature: {feature_name}
PRD: {prd_text[:3000]}
Return exactly:
{{
  "summary": "2-3 sentence feature overview",
  "feature_table": "| Feature | Scope | Priority |\\n| --- | --- | --- |\\n| row | desc | High |",
  "strategy": "Detailed test strategy: functional, regression, edge, non-functional",
  "risks": "Top risks with mitigation",
  "pm_doubts": "1. Question\\n2. Question\\n3. Question"
}}
"""
                raw_audit = call_groq(audit_prompt)
                if not raw_audit: st.stop()
                audit_data = extract_json(raw_audit)
                if not audit_data: st.stop()

            try:
                audit_row = supabase.table("audits").insert({
                    "project_id": project_id, "feature_name": feature_name,
                    "created_by": user["id"],
                    "summary": audit_data.get("summary"),
                    "feature_table": audit_data.get("feature_table"),
                    "strategy": audit_data.get("strategy"),
                    "risks": audit_data.get("risks"),
                    "pm_doubts": audit_data.get("pm_doubts"),
                }).execute().data[0]
                audit_id = audit_row["id"]
            except Exception as e:
                st.error(f"Audit DB save failed: {e}"); st.stop()

            push_notification(user["name"],
                f"generated a QA Audit for **{feature_name}** in **{sel_proj}**",
                "audit", audit_id, project_id, user.get("email",""))
            st.success("✅ Audit saved!")

            with st.expander("📋 View Audit", expanded=True):
                st.subheader("Summary");          st.write(audit_data.get("summary"))
                st.subheader("Feature Breakdown"); st.markdown(audit_data.get("feature_table",""))
                st.subheader("Test Strategy");    st.write(audit_data.get("strategy"))
                st.subheader("Risks");            st.write(audit_data.get("risks"))
                st.subheader("PM Clarifications"); st.write(audit_data.get("pm_doubts"))

            with st.spinner("Step 2/2 — Generating full test coverage…"):
                tc_prompt = f"""
You are a Senior QA Engineer with 10+ years of experience.
Generate a COMPLETE test suite covering every possible scenario for this feature.
Do NOT cap the number. Cover: happy path, negative, edge cases, boundary values,
empty/null inputs, concurrent use, network failure, permissions, UI/UX, performance, regression.
Return ONLY a raw JSON object. All strings single-line. Use \\n for steps. No YAML pipes.
Feature: {feature_name}
PRD: {prd_text[:3000]}
Return:
{{
  "testcases": [
    {{
      "title": "descriptive title",
      "type": "Functional|Regression|Smoke|Edge Case|Negative|Performance|UI",
      "priority": "P0|P1|P2|P3",
      "severity": "Critical|High|Medium|Low",
      "steps": "1. Step\\n2. Step\\n3. Step",
      "expected_result": "what should happen"
    }}
  ]
}}
Priority: P0=blocker, P1=core flows, P2=important, P3=nice-to-have
Severity: Critical=crash/data loss, High=major broken, Medium=partial, Low=cosmetic
"""
                raw_tc = call_groq(tc_prompt)
                if not raw_tc: st.stop()
                tc_data = extract_json(raw_tc)
                if not tc_data or "testcases" not in tc_data:
                    st.error("Could not parse testcases."); st.stop()

            saved, failed_save = [], []
            for tc in tc_data["testcases"]:
                try:
                    supabase.table("testcases").insert({
                        "project_id": project_id, "audit_id": audit_id,
                        "feature_name": feature_name,
                        "title": tc.get("title"), "type": tc.get("type"),
                        "priority": tc.get("priority"), "severity": tc.get("severity"),
                        "steps": tc.get("steps"),
                        "expected_result": tc.get("expected_result"), "status": "Not Run",
                    }).execute()
                    saved.append(tc.get("title","?"))
                except Exception as e:
                    failed_save.append((tc.get("title","?"), str(e)))

            push_notification(user["name"],
                f"generated {len(saved)} test cases for **{feature_name}** in **{sel_proj}**",
                "testcase", project_id=project_id, actor_email=user.get("email",""))
            st.success(f"✅ {len(saved)} test cases saved!")
            if failed_save: st.error(f"❌ {len(failed_save)} failed.")
            st.info("👉 Go to **📁 Testcases** to update status, assign devs, attach evidence.")

    with tab_history:
        audits = supabase.table("audits").select("*").eq("project_id",project_id) \
                     .order("created_at",desc=True).execute().data or []
        if not audits: st.info("No audits yet.")
        for a in audits:
            with st.expander(f"📋 {a.get('feature_name')}  —  {a['created_at'][:10]}"):
                st.write("**Summary:**", a.get("summary"))
                st.write("**Feature Breakdown:**"); st.markdown(a.get("feature_table",""))
                st.write("**Strategy:**", a.get("strategy"))
                st.write("**Risks:**", a.get("risks"))
                st.write("**PM Doubts:**", a.get("pm_doubts"))
                if st.button("🗑 Delete Audit", key=f"del_audit_{a['id']}"):
                    supabase.table("audits").delete().eq("id",a["id"]).execute()
                    st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — TESTCASES
# ═══════════════════════════════════════════════════════════════

elif menu == "📁 Testcases":
    st.title("📁 Testcases")
    require_project()

    c1,c2,c3,c4 = st.columns(4)
    f_status   = c1.selectbox("Status",   ["All","Not Run","Pass","Fail","Blocked"])
    f_priority = c2.selectbox("Priority", ["All","P0","P1","P2","P3"])
    f_severity = c3.selectbox("Severity", ["All","Critical","High","Medium","Low"])
    f_search   = c4.text_input("Search title")

    tcs = supabase.table("testcases").select("*").eq("project_id",project_id) \
              .order("priority").order("created_at").execute().data or []
    if f_status   != "All": tcs = [t for t in tcs if t.get("status")   == f_status]
    if f_priority != "All": tcs = [t for t in tcs if t.get("priority") == f_priority]
    if f_severity != "All": tcs = [t for t in tcs if t.get("severity") == f_severity]
    if f_search:             tcs = [t for t in tcs if f_search.lower() in (t.get("title") or "").lower()]

    all_tcs = supabase.table("testcases").select("status").eq("project_id",project_id).execute().data or []
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total",      len(all_tcs))
    m2.metric("✅ Pass",    sum(1 for t in all_tcs if t["status"]=="Pass"))
    m3.metric("❌ Fail",    sum(1 for t in all_tcs if t["status"]=="Fail"))
    m4.metric("🚫 Blocked", sum(1 for t in all_tcs if t["status"]=="Blocked"))
    m5.metric("⬜ Not Run", sum(1 for t in all_tcs if t["status"]=="Not Run"))
    st.divider()
    st.caption(f"Showing {len(tcs)} test case(s)")

    if not tcs: st.info("No test cases match filters.")
    else:
        for t in tcs:
            tc_id    = t["id"]
            status   = t.get("status","Not Run")
            priority = t.get("priority","P2")
            severity = t.get("severity","Medium")
            label    = (f"{PRIORITY_ICON.get(priority,'⚪')} [{priority}]  "
                        f"{SEVERITY_ICON.get(severity,'⚪')} {t.get('title','Untitled')}"
                        f"  —  {STATUS_ICON.get(status,'')} {status}")

            with st.expander(label):
                col_l,col_r = st.columns(2)
                col_l.write(f"**Type:** {t.get('type','—')}")
                col_r.write(f"**Feature:** {t.get('feature_name','—')}")
                st.write("**Steps:**")
                st.markdown((t.get("steps") or "—").replace("\\n","\n"))
                st.write("**Expected Result:**", t.get("expected_result","—"))
                st.divider()
                st.markdown("**✏️ Update**")
                e1,e2,e3 = st.columns(3)
                new_status   = e1.selectbox("Status",["Not Run","Pass","Fail","Blocked"],
                    index=["Not Run","Pass","Fail","Blocked"].index(status), key=f"st_{tc_id}")
                new_priority = e2.selectbox("Priority",["P0","P1","P2","P3"],
                    index=["P0","P1","P2","P3"].index(priority) if priority in ["P0","P1","P2","P3"] else 2,
                    key=f"pr_{tc_id}")
                new_severity = e3.selectbox("Severity",["Critical","High","Medium","Low"],
                    index=["Critical","High","Medium","Low"].index(severity) if severity in ["Critical","High","Medium","Low"] else 2,
                    key=f"sv_{tc_id}")
                a1,a2 = st.columns(2)
                new_assigned       = a1.text_input("Assigned To (Dev Name)",
                    value=t.get("assigned_to") or "", key=f"as_{tc_id}")
                new_assigned_email = a2.text_input("Dev Email",
                    value=t.get("assigned_email") or "", placeholder="dev@company.com",
                    key=f"ae_{tc_id}")
                new_notes    = st.text_area("Notes / Actual Result",
                    value=t.get("notes") or "", height=80, key=f"nt_{tc_id}")
                new_evidence = st.text_input("Evidence URL",
                    value=t.get("evidence_url") or "", placeholder="https://...",
                    key=f"ev_{tc_id}",
                    disabled=(new_status not in ["Fail","Blocked"]),
                    help="Only needed for Fail/Blocked")

                btn1,btn2,btn3 = st.columns(3)
                with btn1:
                    if st.button("💾 Save", key=f"save_{tc_id}"):
                        old_status = t.get("status","Not Run")
                        supabase.table("testcases").update({
                            "status": new_status, "priority": new_priority,
                            "severity": new_severity,
                            "assigned_to": new_assigned.strip() or None,
                            "assigned_email": new_assigned_email.strip() or None,
                            "notes": new_notes.strip() or None,
                            "evidence_url": new_evidence.strip() or None,
                            "updated_by": user["id"],
                        }).eq("id",tc_id).execute()
                        if new_status != old_status:
                            push_notification(user["name"],
                                f"marked **{t.get('title','')}** as **{new_status}**"
                                + (f" (assigned to {new_assigned})" if new_assigned else ""),
                                "testcase", tc_id, project_id, user.get("email",""))
                        st.success("Saved!"); st.cache_data.clear(); st.rerun()

                with btn2:
                    if new_status == "Fail":
                        if st.button("🐛 Auto Bug Report", key=f"bug_{tc_id}"):
                            existing = supabase.table("bugs").select("id").eq("testcase_id",tc_id).execute().data
                            if existing:
                                st.warning("Bug already exists for this test case.")
                            else:
                                bug_row = supabase.table("bugs").insert({
                                    "project_id": project_id, "testcase_id": tc_id,
                                    "summary": f"[AUTO] {t.get('title')}",
                                    "severity": new_severity, "status": "Open",
                                    "steps": t.get("steps"),
                                    "expected_result": t.get("expected_result"),
                                    "actual_result": new_notes or "See test notes",
                                    "assigned_to": new_assigned.strip() or None,
                                    "assigned_email": new_assigned_email.strip() or None,
                                    "evidence_url": new_evidence.strip() or None,
                                    "reported_by": user["id"],
                                }).execute().data[0]
                                push_notification(user["name"],
                                    f"filed a bug for **{t.get('title','')}**"
                                    + (f" assigned to **{new_assigned}**" if new_assigned else ""),
                                    "bug", bug_row["id"], project_id, user.get("email",""))
                                if new_assigned_email.strip():
                                    cc_key = f"cc_input_{tc_id}"
                                    if cc_key not in st.session_state:
                                        st.session_state[cc_key] = ""
                                    cc_val = st.text_input("CC email (optional)", key=cc_key)
                                    if st.button("📤 Send Email to Dev", key=f"sendemail_{tc_id}"):
                                        ok = send_email(
                                            to_email=new_assigned_email.strip(),
                                            subject=f"[QA] Bug assigned: {t.get('title','')}",
                                            body_html=bug_email_html(t, bug_row, user["name"]),
                                            cc_email=cc_val
                                        )
                                        if ok: st.success(f"✅ Email sent to {new_assigned_email}")
                                else:
                                    st.success("🐛 Bug created! Add dev email to send notification.")

                with btn3:
                    if st.button("🗑 Delete", key=f"del_{tc_id}"):
                        supabase.table("testcases").delete().eq("id",tc_id).execute()
                        st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — BUG CENTER
# ═══════════════════════════════════════════════════════════════

elif menu == "🐛 Bug Center":
    st.title("🐛 Bug Center")
    require_project()

    tab_list,tab_manual = st.tabs(["🐛 All Bugs","➕ Manual Bug"])

    with tab_list:
        fc1,fc2 = st.columns(2)
        f_bsev    = fc1.selectbox("Severity",["All","Critical","High","Medium","Low"],key="bs")
        f_bstatus = fc2.selectbox("Status",  ["All","Open","In Progress","Resolved"],key="bst")

        bugs = supabase.table("bugs").select("*").eq("project_id",project_id) \
                   .order("created_at",desc=True).execute().data or []
        if f_bsev    != "All": bugs = [b for b in bugs if b.get("severity")==f_bsev]
        if f_bstatus != "All": bugs = [b for b in bugs if b.get("status")  ==f_bstatus]

        all_bugs = supabase.table("bugs").select("status,severity").eq("project_id",project_id).execute().data or []
        bm1,bm2,bm3,bm4 = st.columns(4)
        bm1.metric("Total",       len(all_bugs))
        bm2.metric("🔓 Open",    sum(1 for b in all_bugs if b["status"]=="Open"))
        bm3.metric("🔴 Critical", sum(1 for b in all_bugs if b["severity"]=="Critical"))
        bm4.metric("✅ Resolved", sum(1 for b in all_bugs if b["status"]=="Resolved"))
        st.divider()

        if not bugs: st.info("No bugs match filters.")
        else:
            for b in bugs:
                bid   = b["id"]
                label = (f"{SEVERITY_ICON.get(b.get('severity',''),'⚪')} {b.get('summary','?')}"
                         f"  —  {STATUS_ICON.get(b.get('status',''),'⚪')} {b.get('status','')}")
                with st.expander(label):
                    bc1,bc2 = st.columns(2)
                    bc1.write(f"**Severity:** {b.get('severity','—')}")
                    bc2.write(f"**Assigned:** {b.get('assigned_to') or '— unassigned'}")
                    if b.get("assigned_email"): st.caption(f"Dev email: {b['assigned_email']}")
                    st.write("**Steps:**")
                    st.markdown((b.get("steps") or "—").replace("\\n","\n"))
                    st.write("**Expected:**", b.get("expected_result") or "—")
                    st.divider()

                    be1,be2 = st.columns(2)
                    new_bstatus   = be1.selectbox("Status",["Open","In Progress","Resolved"],
                        index=["Open","In Progress","Resolved"].index(b.get("status","Open")),
                        key=f"bst_{bid}")
                    new_bassigned = be2.text_input("Assigned To",
                        value=b.get("assigned_to") or "", key=f"bas_{bid}")
                    new_bemail = st.text_input("Dev Email",
                        value=b.get("assigned_email") or "", key=f"bae_{bid}")
                    new_actual = st.text_area("Actual Result",
                        value=b.get("actual_result") or "", height=80, key=f"bac_{bid}")
                    new_bev = st.text_input("Evidence URL",
                        value=b.get("evidence_url") or "", key=f"bev_{bid}")

                    bb1,bb2,bb3 = st.columns(3)
                    with bb1:
                        if st.button("💾 Update", key=f"bupd_{bid}"):
                            old_bstatus = b.get("status","Open")
                            supabase.table("bugs").update({
                                "status": new_bstatus,
                                "assigned_to": new_bassigned.strip() or None,
                                "assigned_email": new_bemail.strip() or None,
                                "actual_result": new_actual.strip() or None,
                                "evidence_url": new_bev.strip() or None,
                            }).eq("id",bid).execute()
                            if new_bstatus != old_bstatus:
                                push_notification(user["name"],
                                    f"updated bug **{b.get('summary','')}** to **{new_bstatus}**",
                                    "bug", bid, project_id, user.get("email",""))
                            st.success("Updated!"); st.rerun()
                    with bb2:
                        if new_bemail.strip() and st.button("📧 Notify Dev", key=f"bnotify_{bid}"):
                            ok = send_email(
                                to_email=new_bemail.strip(),
                                subject=f"[QA] Bug assigned: {b.get('summary','')}",
                                body_html=bug_email_html({"feature_name":sel_proj}, b, user["name"])
                            )
                            if ok: st.success("Email sent!")
                    with bb3:
                        if st.button("🗑 Delete", key=f"bdel_{bid}"):
                            supabase.table("bugs").delete().eq("id",bid).execute()
                            st.rerun()
                    if b.get("evidence_url"):
                        st.markdown(f"📎 [View Evidence]({b['evidence_url']})")

    with tab_manual:
        st.subheader("Report a Bug Manually")
        m_summary  = st.text_input("Summary *")
        m_sev      = st.selectbox("Severity",["High","Critical","Medium","Low"])
        m_steps    = st.text_area("Steps to Reproduce *", height=120)
        m_expected = st.text_area("Expected Result", height=80)
        m_actual   = st.text_area("Actual Result",   height=80)
        m_assigned = st.text_input("Assigned To (Dev Name)")
        m_devemail = st.text_input("Dev Email (for notification)")
        m_evidence = st.text_input("Evidence URL")
        m_cc       = st.text_input("CC Email (optional)")

        if st.button("🐛 Report Bug", type="primary"):
            missing = validate(summary=m_summary, steps=m_steps)
            if missing: st.error(f"Fill in: {', '.join(missing)}")
            else:
                bug_row = supabase.table("bugs").insert({
                    "project_id": project_id,
                    "summary": m_summary, "severity": m_sev, "status": "Open",
                    "steps": m_steps,
                    "expected_result": m_expected or None,
                    "actual_result": m_actual or None,
                    "assigned_to": m_assigned.strip() or None,
                    "assigned_email": m_devemail.strip() or None,
                    "evidence_url": m_evidence.strip() or None,
                    "reported_by": user["id"],
                }).execute().data[0]
                push_notification(user["name"],
                    f"reported bug **{m_summary}**"
                    + (f" assigned to **{m_assigned}**" if m_assigned else ""),
                    "bug", bug_row["id"], project_id, user.get("email",""))
                if m_devemail.strip():
                    ok = send_email(
                        to_email=m_devemail.strip(),
                        subject=f"[QA] Bug assigned to you: {m_summary}",
                        body_html=bug_email_html({"feature_name":sel_proj}, bug_row, user["name"]),
                        cc_email=m_cc
                    )
                    if ok: st.success(f"✅ Bug reported & email sent to {m_devemail}!")
                    else:  st.success("✅ Bug reported! (Email failed — check Gmail settings)")
                else:
                    st.success("✅ Bug reported!")

# ═══════════════════════════════════════════════════════════════
# PAGE — DASHBOARD
# ═══════════════════════════════════════════════════════════════

elif menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    require_project()

    tcs  = supabase.table("testcases").select("status,priority,severity,type,feature_name") \
               .eq("project_id",project_id).execute().data or []
    bugs = supabase.table("bugs").select("status,severity") \
               .eq("project_id",project_id).execute().data or []

    if not tcs and not bugs:
        st.info("No data yet. Run a Generate & Audit first."); st.stop()

    st.subheader("🧪 Test Execution Summary")
    d1,d2,d3,d4,d5 = st.columns(5)
    d1.metric("Total TCs",  len(tcs))
    d2.metric("✅ Pass",    sum(1 for t in tcs if t["status"]=="Pass"))
    d3.metric("❌ Fail",    sum(1 for t in tcs if t["status"]=="Fail"))
    d4.metric("🚫 Blocked", sum(1 for t in tcs if t["status"]=="Blocked"))
    d5.metric("⬜ Not Run", sum(1 for t in tcs if t["status"]=="Not Run"))

    executed = [t for t in tcs if t["status"] != "Not Run"]
    if executed:
        pass_rate = round(sum(1 for t in executed if t["status"]=="Pass")/len(executed)*100)
        st.progress(pass_rate/100, text=f"Pass Rate: {pass_rate}%  ({len(executed)} executed)")
    st.divider()

    st.subheader("🐛 Bug Summary")
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("Total Bugs",  len(bugs))
    b2.metric("🔓 Open",     sum(1 for b in bugs if b["status"]=="Open"))
    b3.metric("🔴 Critical", sum(1 for b in bugs if b["severity"]=="Critical"))
    b4.metric("✅ Resolved", sum(1 for b in bugs if b["status"]=="Resolved"))
    st.divider()

    col_left,col_right = st.columns(2)
    with col_left:
        st.subheader("By Priority")
        for p in ["P0","P1","P2","P3"]:
            count  = sum(1 for t in tcs if t.get("priority")==p)
            passed = sum(1 for t in tcs if t.get("priority")==p and t["status"]=="Pass")
            st.write(f"{PRIORITY_ICON.get(p,'')} **{p}** — {count} TCs  |  {passed} passed")
    with col_right:
        st.subheader("By Severity")
        for s in ["Critical","High","Medium","Low"]:
            count  = sum(1 for t in tcs if t.get("severity")==s)
            failed = sum(1 for t in tcs if t.get("severity")==s and t["status"]=="Fail")
            st.write(f"{SEVERITY_ICON.get(s,'')} **{s}** — {count} TCs  |  {failed} failed")
    st.divider()

    st.subheader("⚠️ Failed Tests Without Bug Report")
    failed_tcs = supabase.table("testcases").select("id,title,severity,assigned_to") \
                     .eq("project_id",project_id).eq("status","Fail").execute().data or []
    bugged_ids = {b["testcase_id"] for b in
                  supabase.table("bugs").select("testcase_id").eq("project_id",project_id).execute().data or []
                  if b.get("testcase_id")}
    unbugged = [t for t in failed_tcs if t["id"] not in bugged_ids]
    if not unbugged:
        st.success("All failed test cases have bug reports. 🎉")
    else:
        st.warning(f"{len(unbugged)} failed test case(s) missing a bug report:")
        for t in unbugged:
            st.write(f"  {SEVERITY_ICON.get(t.get('severity',''),'⚪')} {t['title']}"
                     f"  — Assigned: {t.get('assigned_to') or 'unassigned'}")
        st.info("👉 Go to **📁 Testcases**, open the failed TC, click **🐛 Auto Bug Report**.")