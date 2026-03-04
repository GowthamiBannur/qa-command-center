import streamlit as st
from supabase import create_client
from groq import Groq
import json

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="QA Command Center",
    page_icon="🧪",
    layout="wide",
)

@st.cache_resource
def init_clients():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    return sb, groq

supabase, groq_client = init_clients()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def extract_json(text: str) -> dict | None:
    """
    Robustly extract a JSON object from model output.
    Handles: markdown fences, unescaped newlines inside strings,
    and trailing commas.
    """
    import re

    # 1. Strip markdown code fences if present (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    # 2. Pull out the outermost { ... } block
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        st.warning("⚠️ Model didn't return JSON. Raw output:")
        st.code(text[:800])
        return None
    raw = text[start:end]

    # 3. First attempt — parse as-is
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 4. Fix unescaped literal newlines inside JSON string values
    #    Replace \n that are NOT already escaped with \\n
    fixed = re.sub(r'(?<!\\)\n', r'\\n', raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ JSON parse error after cleanup: {e}")
        st.code(raw[:1000])
        return None


def call_groq(prompt: str, retries: int = 3) -> str | None:
    """
    Call Groq with automatic retries on empty or whitespace-only responses.
    Uses a system prompt to strongly enforce JSON-only output.
    """
    for attempt in range(1, retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Senior QA Engineer. "
                            "You ALWAYS respond with a single valid JSON object. "
                            "No markdown, no code fences, no explanation — ONLY the raw JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
            st.toast(f"⚠️ Empty response from AI (attempt {attempt}/{retries}), retrying...")
        except Exception as e:
            st.error(f"❌ Groq error on attempt {attempt}: {e}")

    st.error("❌ AI returned empty responses after all retries. Please try again.")
    return None


def validate(**fields) -> list[str]:
    """Return list of field names that are blank."""
    return [name for name, val in fields.items() if not str(val or "").strip()]


@st.cache_data(ttl=30)
def get_projects() -> list[dict]:
    return supabase.table("projects").select("*").order("created_at", desc=True).execute().data or []


def get_project_id(projects: list[dict], name: str) -> str | None:
    for p in projects:
        if p["name"] == name:
            return p["id"]
    return None


def severity_badge(sev: str) -> str:
    colors = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}
    return f"{colors.get(sev, '⚪')} {sev}"


def status_badge(s: str) -> str:
    icons = {"Open": "🔓", "In Progress": "🔄", "Resolved": "✅", "Pass": "✅", "Fail": "❌", "Blocked": "🚫"}
    return f"{icons.get(s, '')} {s}"


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

st.sidebar.title("🧪 QA Command Center")

menu = st.sidebar.radio(
    "Navigate",
    ["📋 Senior QA Audit", "⚙️ AI Testcase Generator", "📁 Testcases", "🐛 Bug Center", "📊 Execution Log"],
)

st.sidebar.divider()

# ── Project management ──
projects = get_projects()
project_names = [p["name"] for p in projects]

selected_project_name = st.sidebar.selectbox(
    "Select Project",
    project_names if project_names else ["— No projects yet —"],
)

project_id = get_project_id(projects, selected_project_name)

with st.sidebar.expander("➕ New Project"):
    new_project_name = st.text_input("Project name", key="new_proj")
    if st.button("Create", key="btn_create_proj"):
        missing = validate(name=new_project_name)
        if missing:
            st.error("Project name cannot be empty.")
        else:
            try:
                supabase.table("projects").insert({"name": new_project_name}).execute()
                st.cache_data.clear()
                st.success(f'Project "{new_project_name}" created!')
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

# ── Guard: no project selected ──
def require_project():
    if not project_id:
        st.info("👈 Select or create a project in the sidebar to continue.")
        st.stop()

# ─────────────────────────────────────────────
# 1️⃣  SENIOR QA AUDIT
# ─────────────────────────────────────────────

if menu == "📋 Senior QA Audit":

    st.title("📋 Senior QA Audit")
    require_project()

    tab_generate, tab_history = st.tabs(["Generate Audit", "Audit History"])

    with tab_generate:
        feature_name = st.text_input("Feature Name *")
        prd_text     = st.text_area("Paste PRD here *", height=250,
                                    placeholder="Paste the full Product Requirements Document...")

        if st.button("🚀 Generate Audit", type="primary"):
            missing = validate(feature_name=feature_name, prd=prd_text)
            if missing:
                st.error(f"Please fill in: {', '.join(missing)}")
                st.stop()

            with st.spinner("Analysing PRD with AI..."):
                prompt = f"""
You are a Senior QA Engineer with 10 years of experience.
Analyse the PRD below and return ONLY a valid JSON object.
Fill EVERY field with detailed, real content. Do NOT leave any value empty or use placeholder text.

Feature: {feature_name}
PRD:
{prd_text[:6000]}

Return exactly this JSON structure:
{{
  "summary": "2-3 sentence overview of the feature and its purpose",
  "feature_table": "markdown table listing each feature/sub-feature with its scope and testing priority",
  "strategy": "detailed test strategy covering functional, regression, edge cases, and non-functional testing",
  "risks": "top 3-5 risk areas with likelihood and mitigation approach",
  "pm_doubts": "numbered list of clarifying questions for the PM that must be answered before testing"
}}
"""
                raw = call_groq(prompt)
                if not raw:
                    st.stop()

                data = extract_json(raw)
                if not data:
                    st.stop()

                # Validate that AI actually filled fields
                empty_fields = [k for k, v in data.items() if not str(v or "").strip()]
                if empty_fields:
                    st.warning(f"⚠️ AI left these fields empty: {empty_fields}. Try again.")
                    st.stop()

                try:
                    supabase.table("audits").insert({
                        "project_id":   project_id,
                        "feature_name": feature_name,
                        "summary":      data.get("summary"),
                        "feature_table":data.get("feature_table"),
                        "strategy":     data.get("strategy"),
                        "risks":        data.get("risks"),
                        "pm_doubts":    data.get("pm_doubts"),
                    }).execute()
                    st.success("✅ Audit saved successfully!")
                except Exception as e:
                    st.error(f"DB save failed: {e}")
                    st.stop()

            st.subheader("📝 Summary")
            st.write(data.get("summary"))

            st.subheader("📊 Feature Breakdown")
            st.markdown(data.get("feature_table"))

            st.subheader("🎯 Test Strategy")
            st.write(data.get("strategy"))

            st.subheader("⚠️ Risks")
            st.write(data.get("risks"))

            st.subheader("❓ PM Clarifications Needed")
            st.write(data.get("pm_doubts"))

    with tab_history:
        audits = supabase.table("audits").select("*") \
                    .eq("project_id", project_id) \
                    .order("created_at", desc=True) \
                    .execute().data or []

        if not audits:
            st.info("No audits yet for this project.")
        else:
            for a in audits:
                with st.expander(f"🗂 {a.get('feature_name', 'Unnamed')}  —  {a['created_at'][:10]}"):
                    st.write("**Summary:**", a.get("summary"))
                    st.write("**Feature Table:**")
                    st.markdown(a.get("feature_table", ""))
                    st.write("**Strategy:**", a.get("strategy"))
                    st.write("**Risks:**", a.get("risks"))
                    st.write("**PM Doubts:**", a.get("pm_doubts"))


# ─────────────────────────────────────────────
# 2️⃣  AI TESTCASE GENERATOR
# ─────────────────────────────────────────────

elif menu == "⚙️ AI Testcase Generator":

    st.title("⚙️ AI Testcase Generator")
    require_project()

    feature_name = st.text_input("Feature Name *")
    prd_text     = st.text_area("Paste PRD Here *", height=250)
    tc_count     = st.slider("Number of test cases to generate", 3, 20, 8)

    if st.button("🚀 Generate Testcases", type="primary"):
        missing = validate(feature_name=feature_name, prd=prd_text)
        if missing:
            st.error(f"Please fill in: {', '.join(missing)}")
            st.stop()

        with st.spinner(f"Generating {tc_count} test cases..."):
            prompt = f"""
You are a Senior QA Engineer. Generate exactly {tc_count} test cases for the feature below.
Return ONLY valid JSON. Populate every field with real content. Do NOT use empty strings.

Feature: {feature_name}
PRD:
{prd_text[:6000]}

Return this JSON structure:
{{
  "testcases": [
    {{
      "title": "clear descriptive test case title",
      "type": "Functional | Regression | Smoke | Edge Case | Negative | Performance | UI",
      "priority": "P0 | P1 | P2 | P3",
      "steps": "1. Step one\\n2. Step two\\n3. Step three",
      "expected_result": "what should happen if the feature works correctly"
    }}
  ]
}}
"""
            raw = call_groq(prompt)
            if not raw:
                st.stop()

            data = extract_json(raw)
            if not data or "testcases" not in data:
                st.error("Could not parse testcases from AI response.")
                st.stop()

        saved, failed = [], []
        for tc in data["testcases"]:
            try:
                supabase.table("testcases").insert({
                    "project_id":      project_id,
                    "feature_name":    feature_name,
                    "title":           tc.get("title"),
                    "type":            tc.get("type"),
                    "priority":        tc.get("priority"),
                    "steps":           tc.get("steps"),
                    "expected_result": tc.get("expected_result"),
                }).execute()
                saved.append(tc.get("title", "Untitled"))
            except Exception as e:
                failed.append((tc.get("title", "?"), str(e)))

        if saved:
            st.success(f"✅ {len(saved)} test case(s) saved!")
            with st.expander("View saved test cases"):
                for title in saved:
                    st.write(f"  • {title}")

        if failed:
            st.error(f"❌ {len(failed)} failed to save:")
            for title, err in failed:
                st.write(f"  • {title}: {err}")


# ─────────────────────────────────────────────
# 3️⃣  TESTCASES VIEW
# ─────────────────────────────────────────────

elif menu == "📁 Testcases":

    st.title("📁 Testcases")
    require_project()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_priority = st.selectbox("Priority", ["All", "P0", "P1", "P2", "P3"])
    with col2:
        filter_type = st.selectbox("Type", ["All", "Functional", "Regression", "Smoke",
                                             "Edge Case", "Negative", "Performance", "UI"])
    with col3:
        search = st.text_input("Search title")

    tcs = supabase.table("testcases").select("*") \
              .eq("project_id", project_id) \
              .order("created_at", desc=True) \
              .execute().data or []

    # Apply filters
    if filter_priority != "All":
        tcs = [t for t in tcs if t.get("priority") == filter_priority]
    if filter_type != "All":
        tcs = [t for t in tcs if t.get("type") == filter_type]
    if search:
        tcs = [t for t in tcs if search.lower() in (t.get("title") or "").lower()]

    st.caption(f"{len(tcs)} test case(s) found")

    if not tcs:
        st.info("No test cases match your filters.")
    else:
        for t in tcs:
            with st.expander(f"[{t.get('priority','?')}] {t.get('title','Untitled')}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Type:** {t.get('type', '—')}")
                c2.write(f"**Priority:** {t.get('priority', '—')}")
                st.write("**Steps:**")
                st.markdown(t.get("steps", "—"))
                st.write("**Expected Result:**", t.get("expected_result", "—"))

                # Delete button
                if st.button("🗑 Delete", key=f"del_tc_{t['id']}"):
                    supabase.table("testcases").delete().eq("id", t["id"]).execute()
                    st.rerun()


# ─────────────────────────────────────────────
# 4️⃣  BUG CENTER
# ─────────────────────────────────────────────

elif menu == "🐛 Bug Center":

    st.title("🐛 Bug Center")
    require_project()

    tab_report, tab_list = st.tabs(["Report Bug", "Bug List"])

    with tab_report:
        summary  = st.text_input("Bug Summary *")
        severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
        status   = st.selectbox("Status", ["Open", "In Progress", "Resolved"])
        steps    = st.text_area("Steps to Reproduce *", height=150,
                                placeholder="1. Go to...\n2. Click on...\n3. Observe...")

        if st.button("🐛 Report Bug", type="primary"):
            missing = validate(summary=summary, steps=steps)
            if missing:
                st.error(f"Please fill in: {', '.join(missing)}")
                st.stop()

            try:
                supabase.table("bugs").insert({
                    "project_id": project_id,
                    "summary":    summary,
                    "severity":   severity,
                    "status":     status,
                    "steps":      steps,
                }).execute()
                st.success("✅ Bug reported!")
            except Exception as e:
                st.error(f"Failed to save: {e}")

    with tab_list:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            f_sev = st.selectbox("Filter Severity", ["All", "Critical", "High", "Medium", "Low"], key="f_sev")
        with col2:
            f_status = st.selectbox("Filter Status", ["All", "Open", "In Progress", "Resolved"], key="f_status")

        bugs = supabase.table("bugs").select("*") \
                   .eq("project_id", project_id) \
                   .order("created_at", desc=True) \
                   .execute().data or []

        if f_sev != "All":
            bugs = [b for b in bugs if b.get("severity") == f_sev]
        if f_status != "All":
            bugs = [b for b in bugs if b.get("status") == f_status]

        st.caption(f"{len(bugs)} bug(s) found")

        if not bugs:
            st.info("No bugs match your filters.")
        else:
            for b in bugs:
                label = f"{severity_badge(b.get('severity','?'))}  ·  {b.get('summary','Untitled')}"
                with st.expander(label):
                    c1, c2 = st.columns(2)
                    c1.write(f"**Severity:** {b.get('severity')}")
                    c2.write(f"**Status:** {status_badge(b.get('status'))}")
                    st.write("**Steps to Reproduce:**")
                    st.markdown(b.get("steps", "—"))

                    # Inline status update
                    new_status = st.selectbox(
                        "Update Status",
                        ["Open", "In Progress", "Resolved"],
                        index=["Open", "In Progress", "Resolved"].index(b.get("status", "Open")),
                        key=f"status_{b['id']}"
                    )
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("💾 Update", key=f"upd_{b['id']}"):
                            supabase.table("bugs").update({"status": new_status}).eq("id", b["id"]).execute()
                            st.rerun()
                    with col_b:
                        if st.button("🗑 Delete", key=f"del_{b['id']}"):
                            supabase.table("bugs").delete().eq("id", b["id"]).execute()
                            st.rerun()


# ─────────────────────────────────────────────
# 5️⃣  EXECUTION LOG
# ─────────────────────────────────────────────

elif menu == "📊 Execution Log":

    st.title("📊 Execution Log")
    require_project()

    tab_log, tab_history = st.tabs(["Log Execution", "History"])

    with tab_log:
        tcs = supabase.table("testcases").select("id, title, priority") \
                  .eq("project_id", project_id) \
                  .order("created_at", desc=True) \
                  .execute().data or []

        if not tcs:
            st.info("No test cases found for this project. Generate some first.")
            st.stop()

        tc_map = {f"[{t.get('priority','?')}] {t['title']}": t["id"] for t in tcs}

        selected_tc_label = st.selectbox("Select Testcase", list(tc_map.keys()))
        status            = st.selectbox("Execution Status", ["Pass", "Fail", "Blocked"])
        executed_by       = st.text_input("Executed By *")
        notes             = st.text_area("Notes / Observations")

        if st.button("📝 Log Execution", type="primary"):
            missing = validate(executed_by=executed_by)
            if missing:
                st.error("Please enter your name in 'Executed By'.")
                st.stop()

            try:
                supabase.table("execution_logs").insert({
                    "project_id":  project_id,
                    "testcase_id": tc_map[selected_tc_label],
                    "status":      status,
                    "executed_by": executed_by,
                    "notes":       notes,
                }).execute()
                st.success("✅ Execution logged!")
            except Exception as e:
                st.error(f"Failed to save: {e}")

    with tab_history:
        logs = supabase.table("execution_logs").select("*") \
                   .eq("project_id", project_id) \
                   .order("executed_on", desc=True) \
                   .execute().data or []

        if not logs:
            st.info("No execution logs yet for this project.")
        else:
            # Summary metrics
            total  = len(logs)
            passed = sum(1 for l in logs if l["status"] == "Pass")
            failed = sum(1 for l in logs if l["status"] == "Fail")
            blocked= sum(1 for l in logs if l["status"] == "Blocked")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Runs", total)
            c2.metric("✅ Pass",    passed,  delta=None)
            c3.metric("❌ Fail",    failed,  delta=None)
            c4.metric("🚫 Blocked", blocked, delta=None)

            st.divider()

            for l in logs:
                label = f"{status_badge(l['status'])}  ·  {l.get('executed_by','?')}  ·  {l['executed_on'][:10]}"
                with st.expander(label):
                    st.write(f"**Status:** {status_badge(l['status'])}")
                    st.write(f"**Executed By:** {l.get('executed_by', '—')}")
                    st.write(f"**Date:** {l.get('executed_on', '—')[:19]}")
                    st.write(f"**Notes:** {l.get('notes') or '—'}")