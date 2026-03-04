import streamlit as st
from supabase import create_client
from groq import Groq
import json, re

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="QA Command Center", page_icon="🧪", layout="wide")

@st.cache_resource
def init_clients():
    sb   = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    return sb, groq

supabase, groq_client = init_clients()

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def extract_json(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        st.warning("⚠️ Model didn't return JSON.")
        st.code(text[:600])
        return None
    raw = text[start:end]
    # attempt 1: as-is
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # attempt 2: fix YAML pipe blocks
    def fix_pipes(s):
        def rep(m):
            lines = [l.strip() for l in m.group(2).split("\n") if l.strip()]
            return f'"{m.group(1)}": "{chr(92)+"n".join(lines)}"'
        return re.sub(r'"(\w+)"\s*:\s*\|\s*\n((?:[ \t]+.+\n?)*)', rep, s)
    raw = fix_pipes(raw)
    # attempt 3: escape bare newlines
    fixed = re.sub(r'(?<!\\)\n', r'\\n', raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ JSON parse error: {e} — try generating again.")
        st.code(raw[:800])
        return None


def call_groq(prompt: str, retries: int = 3) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=4096,
                temperature=0.3,
                messages=[
                    {"role": "system", "content":
                        "You are a Senior QA Engineer. Always respond with ONLY a single raw valid JSON object. "
                        "No markdown, no code fences, no commentary. Never truncate your response."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = resp.choices[0].message.content or ""
            if content.strip():
                return content
            st.toast(f"Empty AI response, retrying ({attempt}/{retries})…")
        except Exception as e:
            st.error(f"Groq error (attempt {attempt}): {e}")
    st.error("AI failed after all retries. Please try again.")
    return None


def validate(**fields) -> list[str]:
    return [k for k, v in fields.items() if not str(v or "").strip()]


@st.cache_data(ttl=30)
def get_projects():
    return supabase.table("projects").select("*").order("created_at", desc=True).execute().data or []


def get_project_id(projects, name):
    return next((p["id"] for p in projects if p["name"] == name), None)


PRIORITY_ICON = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🟢"}
SEVERITY_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
STATUS_ICON   = {"Not Run": "⬜", "Pass": "✅", "Fail": "❌", "Blocked": "🚫",
                 "Open": "🔓", "In Progress": "🔄", "Resolved": "✅"}

def badge(val, mapping):
    return f"{mapping.get(val, '⚪')} {val}"

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

st.sidebar.title("🧪 QA Command Center")
menu = st.sidebar.radio("Navigate", [
    "🚀 Generate & Audit",
    "📁 Testcases",
    "🐛 Bug Center",
    "📊 Dashboard",
])
st.sidebar.divider()

projects      = get_projects()
project_names = [p["name"] for p in projects]

sel_proj = st.sidebar.selectbox(
    "Project",
    project_names if project_names else ["— No projects yet —"]
)
project_id = get_project_id(projects, sel_proj)

with st.sidebar.expander("➕ New Project"):
    new_proj = st.text_input("Name", key="new_proj_input")
    if st.button("Create", key="btn_new_proj"):
        if not new_proj.strip():
            st.error("Name required.")
        else:
            try:
                supabase.table("projects").insert({"name": new_proj.strip()}).execute()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

def require_project():
    if not project_id:
        st.info("👈 Select or create a project first.")
        st.stop()

# ─────────────────────────────────────────────────────────────
# PAGE 1 — GENERATE & AUDIT  (PRD → Audit + Testcases in one go)
# ─────────────────────────────────────────────────────────────

if menu == "🚀 Generate & Audit":
    st.title("🚀 Generate Audit + Testcases")
    require_project()

    tab_gen, tab_history = st.tabs(["📝 New Audit", "🗂 Audit History"])

    # ── NEW AUDIT ──────────────────────────────────────────────
    with tab_gen:
        feature_name = st.text_input("Feature Name *", placeholder="e.g. Search Revamp")
        prd_text     = st.text_area("Paste PRD *", height=260,
                                    placeholder="Paste full PRD here…")
        tc_count     = st.slider("Test cases to generate", 5, 25, 12)

        if st.button("🚀 Generate Audit + Testcases", type="primary"):
            missing = validate(feature=feature_name, prd=prd_text)
            if missing:
                st.error(f"Fill in: {', '.join(missing)}")
                st.stop()

            # ── Step 1: Audit ──────────────────────────────────
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
                if not raw_audit:
                    st.stop()
                audit_data = extract_json(raw_audit)
                if not audit_data:
                    st.stop()

            # Save audit
            try:
                audit_row = supabase.table("audits").insert({
                    "project_id":    project_id,
                    "feature_name":  feature_name,
                    "summary":       audit_data.get("summary"),
                    "feature_table": audit_data.get("feature_table"),
                    "strategy":      audit_data.get("strategy"),
                    "risks":         audit_data.get("risks"),
                    "pm_doubts":     audit_data.get("pm_doubts"),
                }).execute().data[0]
                audit_id = audit_row["id"]
            except Exception as e:
                st.error(f"Audit DB save failed: {e}")
                st.stop()

            st.success("✅ Audit saved!")

            # Show audit
            with st.expander("📋 View Audit", expanded=True):
                st.subheader("Summary")
                st.write(audit_data.get("summary"))
                st.subheader("Feature Breakdown")
                st.markdown(audit_data.get("feature_table", ""))
                st.subheader("Test Strategy")
                st.write(audit_data.get("strategy"))
                st.subheader("Risks")
                st.write(audit_data.get("risks"))
                st.subheader("PM Clarifications Needed")
                st.write(audit_data.get("pm_doubts"))

            # ── Step 2: Testcases ──────────────────────────────
            with st.spinner(f"Step 2/2 — Generating {tc_count} test cases…"):
                tc_prompt = f"""
You are a Senior QA Engineer. Generate exactly {tc_count} test cases covering positive, negative, and edge cases.
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

Priority rules: P0=blocker/critical path, P1=core flows, P2=important, P3=nice-to-have
Severity rules: Critical=app crash/data loss, High=major feature broken, Medium=partial functionality, Low=cosmetic
Cover all: happy path, boundary values, null/empty inputs, concurrent use, network failure, permissions.
"""
                raw_tc = call_groq(tc_prompt)
                if not raw_tc:
                    st.stop()
                tc_data = extract_json(raw_tc)
                if not tc_data or "testcases" not in tc_data:
                    st.error("Could not parse testcases.")
                    st.stop()

            saved, failed = [], []
            for tc in tc_data["testcases"]:
                try:
                    supabase.table("testcases").insert({
                        "project_id":      project_id,
                        "audit_id":        audit_id,
                        "feature_name":    feature_name,
                        "title":           tc.get("title"),
                        "type":            tc.get("type"),
                        "priority":        tc.get("priority"),
                        "severity":        tc.get("severity"),
                        "steps":           tc.get("steps"),
                        "expected_result": tc.get("expected_result"),
                        "status":          "Not Run",
                    }).execute()
                    saved.append(tc.get("title", "?"))
                except Exception as e:
                    failed.append((tc.get("title", "?"), str(e)))

            st.success(f"✅ {len(saved)} test cases saved!")
            if failed:
                st.error(f"❌ {len(failed)} failed: {failed}")

            st.info("👉 Go to **📁 Testcases** to update status, assign devs, and attach evidence.")

    # ── AUDIT HISTORY ──────────────────────────────────────────
    with tab_history:
        audits = supabase.table("audits").select("*") \
                     .eq("project_id", project_id) \
                     .order("created_at", desc=True).execute().data or []
        if not audits:
            st.info("No audits yet.")
        for a in audits:
            with st.expander(f"📋 {a.get('feature_name')}  —  {a['created_at'][:10]}"):
                st.write("**Summary:**", a.get("summary"))
                st.write("**Feature Breakdown:**")
                st.markdown(a.get("feature_table", ""))
                st.write("**Strategy:**", a.get("strategy"))
                st.write("**Risks:**", a.get("risks"))
                st.write("**PM Doubts:**", a.get("pm_doubts"))
                if st.button("🗑 Delete Audit", key=f"del_audit_{a['id']}"):
                    supabase.table("audits").delete().eq("id", a["id"]).execute()
                    st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE 2 — TESTCASES (editable table with status, assignee, evidence, auto bug)
# ─────────────────────────────────────────────────────────────

elif menu == "📁 Testcases":
    st.title("📁 Testcases")
    require_project()

    # ── Filters ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    f_status   = c1.selectbox("Status",   ["All", "Not Run", "Pass", "Fail", "Blocked"])
    f_priority = c2.selectbox("Priority", ["All", "P0", "P1", "P2", "P3"])
    f_severity = c3.selectbox("Severity", ["All", "Critical", "High", "Medium", "Low"])
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
    total   = len(all_tcs)
    passed  = sum(1 for t in all_tcs if t["status"] == "Pass")
    failed  = sum(1 for t in all_tcs if t["status"] == "Fail")
    blocked = sum(1 for t in all_tcs if t["status"] == "Blocked")
    not_run = sum(1 for t in all_tcs if t["status"] == "Not Run")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total",    total)
    m2.metric("✅ Pass",  passed)
    m3.metric("❌ Fail",  failed)
    m4.metric("🚫 Blocked", blocked)
    m5.metric("⬜ Not Run",  not_run)
    st.divider()

    st.caption(f"Showing {len(tcs)} test case(s)")

    if not tcs:
        st.info("No test cases match filters.")
    else:
        for t in tcs:
            tc_id    = t["id"]
            status   = t.get("status", "Not Run")
            priority = t.get("priority", "P2")
            severity = t.get("severity", "Medium")

            label = f"{PRIORITY_ICON.get(priority,'⚪')} [{priority}] {SEVERITY_ICON.get(severity,'⚪')} {t.get('title','Untitled')}  —  {STATUS_ICON.get(status,'')} {status}"

            with st.expander(label):
                # ── Read-only info ────────────────────────────
                col_l, col_r = st.columns(2)
                col_l.write(f"**Type:** {t.get('type','—')}")
                col_r.write(f"**Feature:** {t.get('feature_name','—')}")
                st.write("**Steps:**")
                st.markdown((t.get("steps") or "—").replace("\\n", "\n"))
                st.write("**Expected Result:**", t.get("expected_result", "—"))
                st.divider()

                # ── Editable fields ───────────────────────────
                st.markdown("**✏️ Update**")
                e1, e2, e3 = st.columns(3)
                new_status   = e1.selectbox("Status",
                    ["Not Run", "Pass", "Fail", "Blocked"],
                    index=["Not Run","Pass","Fail","Blocked"].index(status),
                    key=f"st_{tc_id}")
                new_priority = e2.selectbox("Priority",
                    ["P0","P1","P2","P3"],
                    index=["P0","P1","P2","P3"].index(priority) if priority in ["P0","P1","P2","P3"] else 2,
                    key=f"pr_{tc_id}")
                new_severity = e3.selectbox("Severity",
                    ["Critical","High","Medium","Low"],
                    index=["Critical","High","Medium","Low"].index(severity) if severity in ["Critical","High","Medium","Low"] else 2,
                    key=f"sv_{tc_id}")

                new_assigned = st.text_input("Assigned To (Dev Name)",
                    value=t.get("assigned_to") or "",
                    key=f"as_{tc_id}")
                new_notes    = st.text_area("Notes / Observations",
                    value=t.get("notes") or "",
                    height=80, key=f"nt_{tc_id}")

                # Evidence upload (store as Supabase URL or paste link)
                ev_col1, ev_col2 = st.columns(2)
                with ev_col1:
                    new_evidence = st.text_input(
                        "Evidence URL (screenshot/video link)",
                        value=t.get("evidence_url") or "",
                        placeholder="https://...",
                        key=f"ev_{tc_id}",
                        disabled=(new_status not in ["Fail", "Blocked"]),
                        help="Only needed for Fail/Blocked status"
                    )

                # ── Save + Bug buttons ────────────────────────
                btn1, btn2, btn3 = st.columns(3)

                with btn1:
                    if st.button("💾 Save", key=f"save_{tc_id}"):
                        update = {
                            "status":       new_status,
                            "priority":     new_priority,
                            "severity":     new_severity,
                            "assigned_to":  new_assigned.strip() or None,
                            "notes":        new_notes.strip() or None,
                            "evidence_url": new_evidence.strip() or None,
                        }
                        supabase.table("testcases").update(update).eq("id", tc_id).execute()
                        st.success("Saved!")
                        st.cache_data.clear()
                        st.rerun()

                with btn2:
                    # Auto-generate bug report for failed TCs
                    if new_status == "Fail":
                        if st.button("🐛 Auto Bug Report", key=f"bug_{tc_id}"):
                            # check if bug already exists
                            existing = supabase.table("bugs").select("id") \
                                           .eq("testcase_id", tc_id).execute().data
                            if existing:
                                st.warning("Bug already exists for this test case.")
                            else:
                                try:
                                    supabase.table("bugs").insert({
                                        "project_id":      project_id,
                                        "testcase_id":     tc_id,
                                        "summary":         f"[AUTO] {t.get('title')}",
                                        "severity":        new_severity,
                                        "status":          "Open",
                                        "steps":           t.get("steps"),
                                        "expected_result": t.get("expected_result"),
                                        "actual_result":   new_notes or "See test notes",
                                        "assigned_to":     new_assigned.strip() or None,
                                        "evidence_url":    new_evidence.strip() or None,
                                    }).execute()
                                    st.success("🐛 Bug auto-created! View in Bug Center.")
                                except Exception as e:
                                    st.error(f"Bug save failed: {e}")

                with btn3:
                    if st.button("🗑 Delete", key=f"del_{tc_id}"):
                        supabase.table("testcases").delete().eq("id", tc_id).execute()
                        st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE 3 — BUG CENTER
# ─────────────────────────────────────────────────────────────

elif menu == "🐛 Bug Center":
    st.title("🐛 Bug Center")
    require_project()

    tab_list, tab_manual = st.tabs(["🐛 All Bugs", "➕ Manual Bug"])

    # ── ALL BUGS ───────────────────────────────────────────────
    with tab_list:
        fc1, fc2 = st.columns(2)
        f_bsev    = fc1.selectbox("Severity", ["All","Critical","High","Medium","Low"], key="bs")
        f_bstatus = fc2.selectbox("Status",   ["All","Open","In Progress","Resolved"],  key="bst")

        bugs = supabase.table("bugs").select("*") \
                   .eq("project_id", project_id) \
                   .order("created_at", desc=True).execute().data or []

        if f_bsev    != "All": bugs = [b for b in bugs if b.get("severity") == f_bsev]
        if f_bstatus != "All": bugs = [b for b in bugs if b.get("status")   == f_bstatus]

        # metrics
        bm1, bm2, bm3, bm4 = st.columns(4)
        all_bugs = supabase.table("bugs").select("status,severity").eq("project_id", project_id).execute().data or []
        bm1.metric("Total Bugs",  len(all_bugs))
        bm2.metric("🔓 Open",     sum(1 for b in all_bugs if b["status"] == "Open"))
        bm3.metric("🔴 Critical", sum(1 for b in all_bugs if b["severity"] == "Critical"))
        bm4.metric("✅ Resolved", sum(1 for b in all_bugs if b["status"] == "Resolved"))
        st.divider()

        if not bugs:
            st.info("No bugs match filters.")
        else:
            for b in bugs:
                bid   = b["id"]
                label = f"{SEVERITY_ICON.get(b.get('severity',''),'⚪')} {b.get('summary','?')}  —  {STATUS_ICON.get(b.get('status',''),'⚪')} {b.get('status','')}"
                with st.expander(label):
                    bc1, bc2 = st.columns(2)
                    bc1.write(f"**Severity:** {badge(b.get('severity',''), SEVERITY_ICON)}")
                    bc2.write(f"**Assigned To:** {b.get('assigned_to') or '— unassigned'}")

                    st.write("**Steps to Reproduce:**")
                    st.markdown((b.get("steps") or "—").replace("\\n", "\n"))
                    st.write("**Expected Result:**", b.get("expected_result") or "—")

                    # Editable fields
                    st.divider()
                    be1, be2 = st.columns(2)
                    new_bstatus = be1.selectbox("Status",
                        ["Open","In Progress","Resolved"],
                        index=["Open","In Progress","Resolved"].index(b.get("status","Open")),
                        key=f"bst_{bid}")
                    new_bassigned = be2.text_input("Assigned To",
                        value=b.get("assigned_to") or "",
                        key=f"bas_{bid}")
                    new_actual = st.text_area("Actual Result",
                        value=b.get("actual_result") or "",
                        height=80, key=f"bac_{bid}")
                    new_bev = st.text_input("Evidence URL",
                        value=b.get("evidence_url") or "",
                        key=f"bev_{bid}")

                    bb1, bb2 = st.columns(2)
                    with bb1:
                        if st.button("💾 Update Bug", key=f"bupd_{bid}"):
                            supabase.table("bugs").update({
                                "status":        new_bstatus,
                                "assigned_to":   new_bassigned.strip() or None,
                                "actual_result": new_actual.strip() or None,
                                "evidence_url":  new_bev.strip() or None,
                            }).eq("id", bid).execute()
                            st.success("Updated!")
                            st.rerun()
                    with bb2:
                        if st.button("🗑 Delete Bug", key=f"bdel_{bid}"):
                            supabase.table("bugs").delete().eq("id", bid).execute()
                            st.rerun()

                    if b.get("evidence_url"):
                        st.markdown(f"📎 [View Evidence]({b['evidence_url']})")

    # ── MANUAL BUG ─────────────────────────────────────────────
    with tab_manual:
        st.subheader("Report a Bug Manually")
        m_summary  = st.text_input("Summary *")
        m_sev      = st.selectbox("Severity", ["High","Critical","Medium","Low"])
        m_steps    = st.text_area("Steps to Reproduce *", height=120)
        m_expected = st.text_area("Expected Result", height=80)
        m_actual   = st.text_area("Actual Result",   height=80)
        m_assigned = st.text_input("Assigned To")
        m_evidence = st.text_input("Evidence URL")

        if st.button("🐛 Report Bug", type="primary"):
            missing = validate(summary=m_summary, steps=m_steps)
            if missing:
                st.error(f"Fill in: {', '.join(missing)}")
            else:
                try:
                    supabase.table("bugs").insert({
                        "project_id":      project_id,
                        "summary":         m_summary,
                        "severity":        m_sev,
                        "status":          "Open",
                        "steps":           m_steps,
                        "expected_result": m_expected or None,
                        "actual_result":   m_actual or None,
                        "assigned_to":     m_assigned.strip() or None,
                        "evidence_url":    m_evidence.strip() or None,
                    }).execute()
                    st.success("✅ Bug reported!")
                except Exception as e:
                    st.error(f"Failed: {e}")


# ─────────────────────────────────────────────────────────────
# PAGE 4 — DASHBOARD
# ─────────────────────────────────────────────────────────────

elif menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    require_project()

    tcs  = supabase.table("testcases").select("status,priority,severity,type,feature_name") \
               .eq("project_id", project_id).execute().data or []
    bugs = supabase.table("bugs").select("status,severity") \
               .eq("project_id", project_id).execute().data or []

    if not tcs and not bugs:
        st.info("No data yet. Run a Generate & Audit first.")
        st.stop()

    # ── Testcase metrics ───────────────────────────────────────
    st.subheader("🧪 Test Execution Summary")
    d1,d2,d3,d4,d5 = st.columns(5)
    d1.metric("Total TCs",  len(tcs))
    d2.metric("✅ Pass",    sum(1 for t in tcs if t["status"]=="Pass"))
    d3.metric("❌ Fail",    sum(1 for t in tcs if t["status"]=="Fail"))
    d4.metric("🚫 Blocked", sum(1 for t in tcs if t["status"]=="Blocked"))
    d5.metric("⬜ Not Run", sum(1 for t in tcs if t["status"]=="Not Run"))

    # Pass rate
    executed = [t for t in tcs if t["status"] != "Not Run"]
    if executed:
        pass_rate = round(sum(1 for t in executed if t["status"]=="Pass") / len(executed) * 100)
        st.progress(pass_rate / 100, text=f"Pass Rate: {pass_rate}%  ({len(executed)} executed)")

    st.divider()

    # ── Bug metrics ────────────────────────────────────────────
    st.subheader("🐛 Bug Summary")
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("Total Bugs",   len(bugs))
    b2.metric("🔓 Open",      sum(1 for b in bugs if b["status"]=="Open"))
    b3.metric("🔴 Critical",  sum(1 for b in bugs if b["severity"]=="Critical"))
    b4.metric("✅ Resolved",  sum(1 for b in bugs if b["status"]=="Resolved"))

    st.divider()

    # ── Breakdown tables ───────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("By Priority")
        for p in ["P0","P1","P2","P3"]:
            count = sum(1 for t in tcs if t.get("priority")==p)
            passed = sum(1 for t in tcs if t.get("priority")==p and t["status"]=="Pass")
            st.write(f"{PRIORITY_ICON.get(p,'')} **{p}** — {count} TCs  |  {passed} passed")

    with col_right:
        st.subheader("By Severity")
        for s in ["Critical","High","Medium","Low"]:
            count = sum(1 for t in tcs if t.get("severity")==s)
            failed = sum(1 for t in tcs if t.get("severity")==s and t["status"]=="Fail")
            st.write(f"{SEVERITY_ICON.get(s,'')} **{s}** — {count} TCs  |  {failed} failed")

    # ── Failed TCs needing bugs ────────────────────────────────
    st.divider()
    st.subheader("⚠️ Failed Tests Without Bug Report")
    all_tcs_full = supabase.table("testcases").select("id,title,severity,assigned_to") \
                       .eq("project_id", project_id).eq("status", "Fail").execute().data or []
    bugged_tc_ids = {b["testcase_id"] for b in
                     supabase.table("bugs").select("testcase_id")
                     .eq("project_id", project_id).execute().data or []
                     if b.get("testcase_id")}
    unbugged = [t for t in all_tcs_full if t["id"] not in bugged_tc_ids]

    if not unbugged:
        st.success("All failed test cases have bug reports.")
    else:
        st.warning(f"{len(unbugged)} failed test case(s) missing a bug report:")
        for t in unbugged:
            st.write(f"  {SEVERITY_ICON.get(t.get('severity',''),'⚪')} {t['title']}  "
                     f"— Assigned: {t.get('assigned_to') or 'unassigned'}")
        st.info("👉 Go to **📁 Testcases**, open the failed TC, and click **🐛 Auto Bug Report**.")