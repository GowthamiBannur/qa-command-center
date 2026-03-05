import streamlit as st
from supabase import create_client
from groq import Groq
import json, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="QA Command Center", page_icon="🧪", layout="wide")

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
            if content.strip():
                return content
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
        if cc_email.strip():
            msg["Cc"]  = cc_email.strip()
        msg.attach(MIMEText(body_html, "html"))
        recipients = [to_email] + ([cc_email.strip()] if cc_email.strip() else [])
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(st.secrets["GMAIL_ADDRESS"], st.secrets["GMAIL_APP_PASSWORD"])
            srv.sendmail(st.secrets["GMAIL_ADDRESS"], recipients, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Email failed: {e}"); return False


def bug_email_html(tc: dict, bug: dict, reporter_name: str) -> str:
    sev_color = {"Critical": "#dc2626", "High": "#ea580c",
                 "Medium": "#ca8a04", "Low": "#16a34a"}.get(bug.get("severity",""), "#6b7280")
    steps_html = (bug.get("steps") or "—").replace("\\n", "<br>")
    return f"""
<div style="font-family:sans-serif;max-width:600px;margin:auto;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
  <div style="background:#1e293b;padding:20px 24px">
    <h2 style="color:#f8fafc;margin:0">🐛 Bug Assigned to You</h2>
    <p style="color:#94a3b8;margin:4px 0 0">QA Command Center</p>
  </div>
  <div style="padding:24px">
    <p>Hi <strong>{bug.get('assigned_to','Developer')}</strong>,</p>
    <p><strong>{reporter_name}</strong> has assigned a bug to you.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600;width:140px">Summary</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">{bug.get('summary','')}</td></tr>
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600">Severity</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">
            <span style="background:{sev_color};color:#fff;padding:2px 10px;border-radius:12px;font-size:13px">
              {bug.get('severity','')}
            </span></td></tr>
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600">Feature</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">{tc.get('feature_name','—')}</td></tr>
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600">Steps</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">{steps_html}</td></tr>
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600">Expected</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">{bug.get('expected_result','—')}</td></tr>
      <tr><td style="padding:8px;background:#f8fafc;font-weight:600">Actual</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb">{bug.get('actual_result','—')}</td></tr>
      {"<tr><td style='padding:8px;background:#f8fafc;font-weight:600'>Evidence</td><td style='padding:8px'><a href='" + bug.get('evidence_url','') + "'>View Screenshot</a></td></tr>" if bug.get('evidence_url') else ""}
    </table>
    <p style="color:#6b7280;font-size:13px">Please investigate and update the bug status in QA Command Center.</p>
  </div>
</div>"""

# ═══════════════════════════════════════════════════════════════
# HELPERS — NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

def push_notification(actor_name: str, action: str, entity_type: str = "",
                      entity_id: str = None, project_id: str = None, actor_email: str = ""):
    try:
        supabase.table("notifications").insert({
            "actor_name":  actor_name,
            "actor_email": actor_email,
            "action":      action,
            "entity_type": entity_type,
            "entity_id":   entity_id,
            "project_id":  project_id,
        }).execute()
    except Exception:
        pass  # notifications are non-critical


def notification_bell():
    """Render bell icon + unread count in sidebar."""
    notifs = supabase.table("notifications").select("*") \
                 .order("created_at", desc=True).limit(50).execute().data or []
    unread = sum(1 for n in notifs if not n.get("is_read"))
    label  = f"🔔 Notifications ({unread} new)" if unread else "🔔 Notifications"
    with st.sidebar.expander(label):
        if not notifs:
            st.caption("No notifications yet.")
        else:
            if unread and st.button("Mark all read", key="mark_all_read"):
                supabase.table("notifications").update({"is_read": True}) \
                    .eq("is_read", False).execute()
                st.rerun()
            for n in notifs[:20]:
                ts  = n.get("created_at", "")[:16].replace("T", " ")
                dot = "🔵 " if not n.get("is_read") else ""
                st.markdown(f"{dot}**{n['actor_name']}** {n['action']}  \n"
                            f"<span style='color:#9ca3af;font-size:11px'>{ts}</span>",
                            unsafe_allow_html=True)
                st.divider()

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
        st.info("👈 Select or create a project first."); st.stop()

# ═══════════════════════════════════════════════════════════════
# AUTH — SESSION STATE
# ═══════════════════════════════════════════════════════════════

if "user" not in st.session_state:
    st.session_state["user"] = None

user = st.session_state["user"]

# ───────────────────────────────────────────────────────────────
# NOT LOGGED IN — show login / request access
# ───────────────────────────────────────────────────────────────
if not user:
    st.title("🧪 QA Command Center")
    st.markdown("#### Your AI-powered QA workspace")
    st.divider()

    tab_login, tab_request = st.tabs(["🔐 Login", "✋ Request Access"])

    with tab_login:
        st.subheader("Welcome back")
        login_email = st.text_input("Your email", placeholder="you@company.com", key="login_email")
        if st.button("Login", type="primary", key="btn_login"):
            if not login_email.strip():
                st.error("Enter your email.")
            else:
                result = supabase.table("users").select("*") \
                             .eq("email", login_email.strip().lower()).execute().data
                if not result:
                    st.error("No account found. Request access first.")
                elif result[0]["status"] == "pending":
                    st.warning("⏳ Your request is pending approval. We'll notify you soon.")
                elif result[0]["status"] == "rejected":
                    st.error("❌ Your access request was rejected. Contact the admin.")
                else:
                    st.session_state["user"] = result[0]
                    st.toast(f"Welcome back, {result[0]['name']}! 👋", icon="✅")
                    st.rerun()

    with tab_request:
        st.subheader("Request Access")
        st.info("Fill in your details. The admin will approve your request.")
        req_name  = st.text_input("Full Name *", key="req_name")
        req_email = st.text_input("Work Email *", key="req_email")
        if st.button("✋ Submit Access Request", type="primary", key="btn_request"):
            missing = validate(name=req_name, email=req_email)
            if missing:
                st.error(f"Fill in: {', '.join(missing)}")
            else:
                email_clean = req_email.strip().lower()
                existing = supabase.table("users").select("id,status") \
                               .eq("email", email_clean).execute().data
                if existing:
                    s = existing[0]["status"]
                    if s == "approved":
                        st.info("You already have access! Use the Login tab.")
                    elif s == "pending":
                        st.warning("Your request is already pending.")
                    else:
                        st.error("Your request was previously rejected. Contact admin.")
                else:
                    supabase.table("users").insert({
                        "name": req_name.strip(), "email": email_clean,
                        "role": "member", "status": "pending"
                    }).execute()
                    push_notification(
                        actor_name=req_name.strip(),
                        action=f"requested access to QA Command Center",
                        entity_type="user", actor_email=email_clean
                    )
                    # Notify admin via email
                    try:
                        send_email(
                            to_email=st.secrets["GMAIL_ADDRESS"],
                            subject=f"[QA Center] Access request from {req_name.strip()}",
                            body_html=f"""
<div style="font-family:sans-serif;max-width:500px">
  <h3>New Access Request</h3>
  <p><b>Name:</b> {req_name.strip()}<br><b>Email:</b> {email_clean}</p>
  <p>Log in as admin to approve or reject this request.</p>
</div>"""
                        )
                    except Exception:
                        pass
                    st.success("✅ Request submitted! The admin will review it shortly.")
    st.stop()

# ═══════════════════════════════════════════════════════════════
# LOGGED IN — MAIN APP
# ═══════════════════════════════════════════════════════════════

is_admin = user.get("role") == "admin"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

st.sidebar.title("🧪 QA Command Center")
st.sidebar.caption(f"👤 {user['name']}  ·  {'🛡 Admin' if is_admin else '👥 Member'}")
st.sidebar.divider()

nav_options = ["🚀 Generate & Audit", "📁 Testcases", "🐛 Bug Center", "📊 Dashboard"]
if is_admin:
    nav_options += ["👥 Team Access"]

menu = st.sidebar.radio("Navigate", nav_options)
st.sidebar.divider()

# Notifications bell
notification_bell()
st.sidebar.divider()

# Project picker
projects      = get_projects()
project_names = [p["name"] for p in projects]
_auto         = st.session_state.pop("_auto_select_proj", None)
_proj_list    = project_names if project_names else ["— No projects yet —"]
_default_idx  = _proj_list.index(_auto) if (_auto and _auto in _proj_list) else 0

sel_proj   = st.sidebar.selectbox("Project", _proj_list, index=_default_idx)
project_id = get_project_id(projects, sel_proj)
st.session_state["project_id"] = project_id

if project_id:
    st.sidebar.success(f"📂 {sel_proj}")

with st.sidebar.expander("➕ New Project"):
    new_proj = st.text_input("Name", key="new_proj_input", placeholder="e.g. Search Revamp v2")
    if st.button("✅ Create Project", key="btn_new_proj", type="primary"):
        name = new_proj.strip()
        if not name:
            st.error("Name cannot be empty.")
        elif name in project_names:
            st.warning(f'"{name}" already exists — select it above.')
        else:
            try:
                supabase.table("projects").insert({
                    "name": name, "created_by": user["id"]
                }).execute()
                push_notification(user["name"], f"created project **{name}**",
                                  "project", actor_email=user["email"])
                st.cache_data.clear()
                st.session_state["_auto_select_proj"] = name
                st.toast(f'Project "{name}" created!', icon="🎉")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# Logout
st.sidebar.divider()
if st.sidebar.button("🚪 Logout"):
    st.session_state["user"] = None
    st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — ADMIN: TEAM ACCESS
# ═══════════════════════════════════════════════════════════════

if menu == "👥 Team Access" and is_admin:
    st.title("👥 Team Access Management")

    tab_pending, tab_all = st.tabs(["⏳ Pending Requests", "👥 All Members"])

    with tab_pending:
        pending = supabase.table("users").select("*").eq("status","pending") \
                      .order("created_at").execute().data or []
        if not pending:
            st.success("No pending requests.")
        else:
            st.info(f"{len(pending)} request(s) waiting for approval.")
            for u in pending:
                with st.expander(f"✋ {u['name']}  ·  {u['email']}  ·  {u['created_at'][:10]}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Approve", key=f"apr_{u['id']}", type="primary"):
                            supabase.table("users").update({"status":"approved"}).eq("id",u["id"]).execute()
                            push_notification(user["name"],
                                f"approved access for **{u['name']}**", "user")
                            send_email(
                                to_email=u["email"],
                                subject="✅ Your QA Command Center access is approved!",
                                body_html=f"""
<div style="font-family:sans-serif;max-width:500px">
  <h3>🎉 Access Approved!</h3>
  <p>Hi <b>{u['name']}</b>,</p>
  <p>Your request to join <b>QA Command Center</b> has been approved.</p>
  <p>Log in with your email: <b>{u['email']}</b></p>
</div>"""
                            )
                            st.success(f"Approved! Email sent to {u['email']}.")
                            st.rerun()
                    with c2:
                        if st.button("❌ Reject", key=f"rej_{u['id']}"):
                            supabase.table("users").update({"status":"rejected"}).eq("id",u["id"]).execute()
                            send_email(
                                to_email=u["email"],
                                subject="QA Command Center — Access Request Update",
                                body_html=f"""
<div style="font-family:sans-serif;max-width:500px">
  <p>Hi <b>{u['name']}</b>,</p>
  <p>Your access request was not approved at this time. Contact the admin for more info.</p>
</div>"""
                            )
                            st.rerun()

    with tab_all:
        all_users = supabase.table("users").select("*").order("created_at").execute().data or []
        for u in all_users:
            status_icon = {"approved":"✅","pending":"⏳","rejected":"❌"}.get(u["status"],"❓")
            role_icon   = "🛡" if u["role"]=="admin" else "👤"
            with st.expander(f"{status_icon} {role_icon} {u['name']}  ·  {u['email']}"):
                st.write(f"**Status:** {u['status']}  |  **Role:** {u['role']}")
                st.write(f"**Joined:** {u['created_at'][:10]}")
                if u["id"] != user["id"]:
                    mc1, mc2, mc3 = st.columns(3)
                    with mc1:
                        new_role = "member" if u["role"]=="admin" else "admin"
                        if st.button(f"Make {new_role}", key=f"role_{u['id']}"):
                            supabase.table("users").update({"role":new_role}).eq("id",u["id"]).execute()
                            st.rerun()
                    with mc2:
                        if u["status"] == "approved" and st.button("Revoke", key=f"rev_{u['id']}"):
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
            if missing:
                st.error(f"Fill in: {', '.join(missing)}"); st.stop()

            # Step 1: Audit
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
                "audit", audit_id, project_id, user["email"])

            st.success("✅ Audit saved!")
            with st.expander("📋 View Audit", expanded=True):
                st.subheader("Summary");         st.write(audit_data.get("summary"))
                st.subheader("Feature Breakdown"); st.markdown(audit_data.get("feature_table",""))
                st.subheader("Test Strategy");    st.write(audit_data.get("strategy"))
                st.subheader("Risks");            st.write(audit_data.get("risks"))
                st.subheader("PM Clarifications"); st.write(audit_data.get("pm_doubts"))

            # Step 2: Testcases
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
                "testcase", project_id=project_id, actor_email=user["email"])

            st.success(f"✅ {len(saved)} test cases saved!")
            if failed_save:
                st.error(f"❌ {len(failed_save)} failed: {failed_save}")
            st.info("👉 Go to **📁 Testcases** to update status, assign devs, and attach evidence.")

    with tab_history:
        audits = supabase.table("audits").select("*") \
                     .eq("project_id", project_id).order("created_at", desc=True).execute().data or []
        if not audits:
            st.info("No audits yet.")
        for a in audits:
            with st.expander(f"📋 {a.get('feature_name')}  —  {a['created_at'][:10]}"):
                st.write("**Summary:**", a.get("summary"))
                st.write("**Feature Breakdown:**"); st.markdown(a.get("feature_table",""))
                st.write("**Strategy:**", a.get("strategy"))
                st.write("**Risks:**", a.get("risks"))
                st.write("**PM Doubts:**", a.get("pm_doubts"))
                if st.button("🗑 Delete Audit", key=f"del_audit_{a['id']}"):
                    supabase.table("audits").delete().eq("id", a["id"]).execute()
                    st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — TESTCASES
# ═══════════════════════════════════════════════════════════════

elif menu == "📁 Testcases":
    st.title("📁 Testcases")
    require_project()

    # Filters
    c1, c2, c3, c4 = st.columns(4)
    f_status   = c1.selectbox("Status",   ["All","Not Run","Pass","Fail","Blocked"])
    f_priority = c2.selectbox("Priority", ["All","P0","P1","P2","P3"])
    f_severity = c3.selectbox("Severity", ["All","Critical","High","Medium","Low"])
    f_search   = c4.text_input("Search title")

    tcs = supabase.table("testcases").select("*") \
              .eq("project_id", project_id) \
              .order("priority").order("created_at").execute().data or []

    if f_status   != "All": tcs = [t for t in tcs if t.get("status")   == f_status]
    if f_priority != "All": tcs = [t for t in tcs if t.get("priority") == f_priority]
    if f_severity != "All": tcs = [t for t in tcs if t.get("severity") == f_severity]
    if f_search:             tcs = [t for t in tcs if f_search.lower() in (t.get("title") or "").lower()]

    # Summary bar
    all_tcs = supabase.table("testcases").select("status") \
                  .eq("project_id", project_id).execute().data or []
    total = len(all_tcs)
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total",      total)
    m2.metric("✅ Pass",    sum(1 for t in all_tcs if t["status"]=="Pass"))
    m3.metric("❌ Fail",    sum(1 for t in all_tcs if t["status"]=="Fail"))
    m4.metric("🚫 Blocked", sum(1 for t in all_tcs if t["status"]=="Blocked"))
    m5.metric("⬜ Not Run", sum(1 for t in all_tcs if t["status"]=="Not Run"))
    st.divider()
    st.caption(f"Showing {len(tcs)} test case(s)")

    if not tcs:
        st.info("No test cases match filters.")
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
                col_l, col_r = st.columns(2)
                col_l.write(f"**Type:** {t.get('type','—')}")
                col_r.write(f"**Feature:** {t.get('feature_name','—')}")
                st.write("**Steps:**")
                st.markdown((t.get("steps") or "—").replace("\\n","\n"))
                st.write("**Expected Result:**", t.get("expected_result","—"))
                st.divider()

                # Editable
                st.markdown("**✏️ Update**")
                e1, e2, e3 = st.columns(3)
                new_status   = e1.selectbox("Status",
                    ["Not Run","Pass","Fail","Blocked"],
                    index=["Not Run","Pass","Fail","Blocked"].index(status),
                    key=f"st_{tc_id}")
                new_priority = e2.selectbox("Priority", ["P0","P1","P2","P3"],
                    index=["P0","P1","P2","P3"].index(priority) if priority in ["P0","P1","P2","P3"] else 2,
                    key=f"pr_{tc_id}")
                new_severity = e3.selectbox("Severity", ["Critical","High","Medium","Low"],
                    index=["Critical","High","Medium","Low"].index(severity) if severity in ["Critical","High","Medium","Low"] else 2,
                    key=f"sv_{tc_id}")

                a1, a2 = st.columns(2)
                new_assigned       = a1.text_input("Assigned To (Dev Name)",
                    value=t.get("assigned_to") or "", key=f"as_{tc_id}")
                new_assigned_email = a2.text_input("Dev Email (for notifications)",
                    value=t.get("assigned_email") or "", key=f"ae_{tc_id}",
                    placeholder="dev@company.com")
                new_notes = st.text_area("Notes / Actual Result",
                    value=t.get("notes") or "", height=80, key=f"nt_{tc_id}")
                new_evidence = st.text_input(
                    "Evidence URL (screenshot/video link)",
                    value=t.get("evidence_url") or "", placeholder="https://...",
                    key=f"ev_{tc_id}",
                    disabled=(new_status not in ["Fail","Blocked"]),
                    help="Only needed for Fail/Blocked")

                btn1, btn2, btn3 = st.columns(3)

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
                        }).eq("id", tc_id).execute()

                        if new_status != old_status:
                            push_notification(user["name"],
                                f"marked **{t.get('title','')}** as **{new_status}**"
                                + (f" (assigned to {new_assigned})" if new_assigned else ""),
                                "testcase", tc_id, project_id, user["email"])

                        st.success("Saved!"); st.cache_data.clear(); st.rerun()

                with btn2:
                    if new_status == "Fail":
                        if st.button("🐛 Auto Bug Report", key=f"bug_{tc_id}"):
                            existing = supabase.table("bugs").select("id") \
                                           .eq("testcase_id", tc_id).execute().data
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
                                    "bug", bug_row["id"], project_id, user["email"])

                                # Send email to assigned dev
                                if new_assigned_email.strip():
                                    with st.form(key=f"email_form_{tc_id}"):
                                        st.markdown(f"📧 Send bug notification to **{new_assigned}** ({new_assigned_email})?")
                                        cc_email = st.text_input("CC (optional)", placeholder="manager@company.com")
                                        send_now = st.form_submit_button("📤 Send Email Notification")
                                        if send_now:
                                            ok = send_email(
                                                to_email=new_assigned_email.strip(),
                                                subject=f"[QA] Bug assigned to you: {t.get('title','')}",
                                                body_html=bug_email_html(t, bug_row, user["name"]),
                                                cc_email=cc_email
                                            )
                                            if ok:
                                                st.success(f"✅ Email sent to {new_assigned_email}")
                                else:
                                    st.success("🐛 Bug created! Add dev email above to send notification.")

                with btn3:
                    if st.button("🗑 Delete", key=f"del_{tc_id}"):
                        supabase.table("testcases").delete().eq("id", tc_id).execute()
                        st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE — BUG CENTER
# ═══════════════════════════════════════════════════════════════

elif menu == "🐛 Bug Center":
    st.title("🐛 Bug Center")
    require_project()

    tab_list, tab_manual = st.tabs(["🐛 All Bugs", "➕ Manual Bug"])

    with tab_list:
        fc1, fc2 = st.columns(2)
        f_bsev    = fc1.selectbox("Severity", ["All","Critical","High","Medium","Low"], key="bs")
        f_bstatus = fc2.selectbox("Status",   ["All","Open","In Progress","Resolved"],  key="bst")

        bugs = supabase.table("bugs").select("*") \
                   .eq("project_id", project_id).order("created_at", desc=True).execute().data or []
        if f_bsev    != "All": bugs = [b for b in bugs if b.get("severity") == f_bsev]
        if f_bstatus != "All": bugs = [b for b in bugs if b.get("status")   == f_bstatus]

        all_bugs = supabase.table("bugs").select("status,severity").eq("project_id",project_id).execute().data or []
        bm1,bm2,bm3,bm4 = st.columns(4)
        bm1.metric("Total",      len(all_bugs))
        bm2.metric("🔓 Open",   sum(1 for b in all_bugs if b["status"]=="Open"))
        bm3.metric("🔴 Critical",sum(1 for b in all_bugs if b["severity"]=="Critical"))
        bm4.metric("✅ Resolved",sum(1 for b in all_bugs if b["status"]=="Resolved"))
        st.divider()

        if not bugs:
            st.info("No bugs match filters.")
        else:
            for b in bugs:
                bid   = b["id"]
                label = (f"{SEVERITY_ICON.get(b.get('severity',''),'⚪')} {b.get('summary','?')}  "
                         f"—  {STATUS_ICON.get(b.get('status',''),'⚪')} {b.get('status','')}")
                with st.expander(label):
                    bc1, bc2 = st.columns(2)
                    bc1.write(f"**Severity:** {b.get('severity','—')}")
                    bc2.write(f"**Assigned To:** {b.get('assigned_to') or '— unassigned'}")
                    if b.get("assigned_email"):
                        st.caption(f"Dev email: {b['assigned_email']}")
                    st.write("**Steps:**")
                    st.markdown((b.get("steps") or "—").replace("\\n","\n"))
                    st.write("**Expected:**", b.get("expected_result") or "—")
                    st.divider()

                    be1, be2 = st.columns(2)
                    new_bstatus   = be1.selectbox("Status",
                        ["Open","In Progress","Resolved"],
                        index=["Open","In Progress","Resolved"].index(b.get("status","Open")),
                        key=f"bst_{bid}")
                    new_bassigned = be2.text_input("Assigned To",
                        value=b.get("assigned_to") or "", key=f"bas_{bid}")
                    new_bemail    = st.text_input("Dev Email",
                        value=b.get("assigned_email") or "", key=f"bae_{bid}")
                    new_actual    = st.text_area("Actual Result",
                        value=b.get("actual_result") or "", height=80, key=f"bac_{bid}")
                    new_bev       = st.text_input("Evidence URL",
                        value=b.get("evidence_url") or "", key=f"bev_{bid}")

                    bb1, bb2, bb3 = st.columns(3)
                    with bb1:
                        if st.button("💾 Update", key=f"bupd_{bid}"):
                            old_bstatus = b.get("status","Open")
                            supabase.table("bugs").update({
                                "status": new_bstatus,
                                "assigned_to": new_bassigned.strip() or None,
                                "assigned_email": new_bemail.strip() or None,
                                "actual_result": new_actual.strip() or None,
                                "evidence_url": new_bev.strip() or None,
                            }).eq("id", bid).execute()
                            if new_bstatus != old_bstatus:
                                push_notification(user["name"],
                                    f"updated bug **{b.get('summary','')}** to **{new_bstatus}**",
                                    "bug", bid, project_id, user["email"])
                            st.success("Updated!"); st.rerun()
                    with bb2:
                        if new_bemail.strip() and st.button("📧 Notify Dev", key=f"bnotify_{bid}"):
                            cc = st.text_input("CC email", key=f"bcc_{bid}")
                            ok = send_email(
                                to_email=new_bemail.strip(),
                                subject=f"[QA] Bug assigned: {b.get('summary','')}",
                                body_html=bug_email_html(
                                    {"feature_name": sel_proj}, b, user["name"]),
                                cc_email=cc
                            )
                            if ok: st.success("Email sent!")
                    with bb3:
                        if st.button("🗑 Delete", key=f"bdel_{bid}"):
                            supabase.table("bugs").delete().eq("id", bid).execute()
                            st.rerun()

                    if b.get("evidence_url"):
                        st.markdown(f"📎 [View Evidence]({b['evidence_url']})")

    with tab_manual:
        st.subheader("Report a Bug Manually")
        m_summary  = st.text_input("Summary *")
        m_sev      = st.selectbox("Severity", ["High","Critical","Medium","Low"])
        m_steps    = st.text_area("Steps to Reproduce *", height=120)
        m_expected = st.text_area("Expected Result", height=80)
        m_actual   = st.text_area("Actual Result",   height=80)
        m_assigned = st.text_input("Assigned To (Dev Name)")
        m_devemail = st.text_input("Dev Email (for notification)")
        m_evidence = st.text_input("Evidence URL")
        m_cc       = st.text_input("CC Email (optional)")

        if st.button("🐛 Report Bug", type="primary"):
            missing = validate(summary=m_summary, steps=m_steps)
            if missing:
                st.error(f"Fill in: {', '.join(missing)}")
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
                    "bug", bug_row["id"], project_id, user["email"])

                if m_devemail.strip():
                    ok = send_email(
                        to_email=m_devemail.strip(),
                        subject=f"[QA] Bug assigned to you: {m_summary}",
                        body_html=bug_email_html(
                            {"feature_name": sel_proj}, bug_row, user["name"]),
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
               .eq("project_id", project_id).execute().data or []
    bugs = supabase.table("bugs").select("status,severity") \
               .eq("project_id", project_id).execute().data or []

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
        pass_rate = round(sum(1 for t in executed if t["status"]=="Pass") / len(executed) * 100)
        st.progress(pass_rate/100, text=f"Pass Rate: {pass_rate}%  ({len(executed)} executed)")
    st.divider()

    st.subheader("🐛 Bug Summary")
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("Total Bugs",   len(bugs))
    b2.metric("🔓 Open",      sum(1 for b in bugs if b["status"]=="Open"))
    b3.metric("🔴 Critical",  sum(1 for b in bugs if b["severity"]=="Critical"))
    b4.metric("✅ Resolved",  sum(1 for b in bugs if b["status"]=="Resolved"))
    st.divider()

    col_left, col_right = st.columns(2)
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
                     .eq("project_id", project_id).eq("status","Fail").execute().data or []
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