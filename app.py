import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client

# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------
st.set_page_config(
    page_title="Principal QA Strategy Hub",
    layout="wide",
    page_icon="🛡️"
)

# ----------------------------------------------------
# CONNECTIONS
# ----------------------------------------------------
@st.cache_resource
def init_connection():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = init_connection()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=st.secrets["GROQ_API_KEY"]
)

# ----------------------------------------------------
# SESSION INITIALIZATION (SAFE)
# ----------------------------------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.rewrite = ""
    st.session_state.feature_table = ""
    st.session_state.strategy = ""
    st.session_state.doubts = ""
    st.session_state.current_df = pd.DataFrame()
    st.session_state.active_project = None
    st.session_state.project_id = None
    st.session_state.loaded_project = None

# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
def ensure_columns(df):
    required = [
        "ID", "Scenario", "Expected", "Status",
        "Severity", "Priority", "Module",
        "Assigned_To", "Actual_Result", "Evidence_Link"
    ]

    for col in required:
        if col not in df.columns:
            df[col] = ""

    if "Status" in df.columns:
        df["Status"] = df["Status"].replace("", "Pending")

    return df


def get_projects():
    res = supabase.table("projects").select("*").execute()
    return res.data if res.data else []


def create_project(name):
    supabase.table("projects").insert({"name": name}).execute()


def get_project_id(name):
    res = supabase.table("projects").select("id").eq("name", name).execute()
    return res.data[0]["id"] if res.data else None


def parse_sections(text):
    sections = {
        "rewrite": "",
        "feature_table": "",
        "strategy": "",
        "doubts": ""
    }

    current = None

    for line in text.split("\n"):
        upper = line.upper()

        if "REWRITE" in upper:
            current = "rewrite"
        elif "FEATURE_TABLE" in upper:
            current = "feature_table"
        elif "STRATEGY" in upper and "TEST_CASES" not in upper:
            current = "strategy"
        elif "DOUBTS" in upper:
            current = "doubts"
        elif current:
            sections[current] += line + "\n"

    return sections


# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------
with st.sidebar:
    st.title("👥 Team QA Hub")

    projects = get_projects()
    project_names = [p["name"] for p in projects]

    selected = st.selectbox(
        "Switch Project",
        options=project_names + ["+ New Project"]
    )

    if selected == "+ New Project":
        new_name = st.text_input("New Project Name")
        if st.button("Create Project"):
            create_project(new_name)
            st.success("Project Created")
            st.rerun()
    else:
        st.session_state.active_project = selected
        st.session_state.project_id = get_project_id(selected)

# ----------------------------------------------------
# LOAD DATA ONLY WHEN PROJECT CHANGES
# ----------------------------------------------------
if (
    st.session_state.active_project
    and st.session_state.active_project != st.session_state.loaded_project
):

    pid = st.session_state.project_id

    # Load Strategy
    strat = supabase.table("strategies") \
        .select("*") \
        .eq("project_id", pid) \
        .execute()

    if strat.data:
        data = strat.data[0]
        st.session_state.rewrite = data.get("rewrite", "")
        st.session_state.feature_table = data.get("feature_table", "")
        st.session_state.strategy = data.get("strategy_text", "")
        st.session_state.doubts = data.get("doubts", "")
    else:
        st.session_state.rewrite = ""
        st.session_state.feature_table = ""
        st.session_state.strategy = ""
        st.session_state.doubts = ""

    # Load Test Cases
    cases = supabase.table("test_cases") \
        .select("*") \
        .eq("project_id", pid) \
        .execute()

    if cases.data:
        df = pd.DataFrame(cases.data)

        df = df.rename(columns={
            "case_id": "ID",
            "scenario": "Scenario",
            "expected": "Expected",
            "status": "Status",
            "severity": "Severity",
            "priority": "Priority",
            "module": "Module",
            "assigned_to": "Assigned_To",
            "actual_result": "Actual_Result",
            "evidence_link": "Evidence_Link"
        })

        st.session_state.current_df = ensure_columns(df)
    else:
        st.session_state.current_df = ensure_columns(pd.DataFrame())

    st.session_state.loaded_project = st.session_state.active_project

# ----------------------------------------------------
# TABS
# ----------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "🏗️ Senior QA Audit & Strategy",
    "✅ Execution Log",
    "🐞 Bug Center"
])

# ----------------------------------------------------
# TAB 1 - STRATEGY
# ----------------------------------------------------
with tab1:

    st.subheader("📋 Test Strategy & Quality Gate")

    prd_text = st.text_area("Paste PRD Document", height=200)

    if st.button("🚀 Generate Quality Strategy"):

        if not prd_text.strip():
            st.warning("Please enter PRD.")
            st.stop()

        prompt = f"""
        Analyze PRD:

        1. REWRITE
        2. FEATURE_TABLE
        3. STRATEGY
        4. DOUBTS
        5. TEST_CASES (35+)

        Format test cases:
        CASE: Scenario | Expected | Severity | Priority

        PRD:
        {prd_text}
        """

        with st.spinner("Generating..."):

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.choices[0].message.content

            sections = parse_sections(result)

            st.session_state.rewrite = sections["rewrite"]
            st.session_state.feature_table = sections["feature_table"]
            st.session_state.strategy = sections["strategy"]
            st.session_state.doubts = sections["doubts"]

            # Parse Test Cases
            pattern = r"CASE:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)$"
            matches = re.findall(pattern, result, re.MULTILINE)

            rows = []
            for i, match in enumerate(matches):
                scenario, expected, severity, priority = match

                rows.append({
                    "ID": f"TC-{i+1}",
                    "Scenario": scenario.strip(),
                    "Expected": expected.strip(),
                    "Status": "Pending",
                    "Severity": severity.strip(),
                    "Priority": priority.strip(),
                    "Module": "",
                    "Assigned_To": "",
                    "Actual_Result": "",
                    "Evidence_Link": ""
                })

            st.session_state.current_df = ensure_columns(pd.DataFrame(rows))

    # Only show sections if content exists
    if any([
        st.session_state.rewrite,
        st.session_state.feature_table,
        st.session_state.strategy,
        st.session_state.doubts
    ]):

        st.markdown("## 1️⃣ REWRITE")
        st.markdown(st.session_state.rewrite)

        st.markdown("## 2️⃣ FEATURE TABLE")
        st.markdown(st.session_state.feature_table)

        st.markdown("## 3️⃣ STRATEGY")
        st.markdown(st.session_state.strategy)

        st.markdown("## 4️⃣ DOUBTS")
        st.markdown(st.session_state.doubts)

        if st.button("💾 Save Strategy"):
            pid = st.session_state.project_id

            supabase.table("strategies") \
                .delete() \
                .eq("project_id", pid) \
                .execute()

            supabase.table("strategies").insert({
                "project_id": pid,
                "prd_text": prd_text,
                "strategy_text": st.session_state.strategy,
                "rewrite": st.session_state.rewrite,
                "feature_table": st.session_state.feature_table,
                "doubts": st.session_state.doubts
            }).execute()

            st.success("Strategy Saved")

# ----------------------------------------------------
# TAB 2 - EXECUTION LOG
# ----------------------------------------------------
with tab2:

    st.subheader("Execution Log")

    st.session_state.current_df = st.data_editor(
        st.session_state.current_df,
        use_container_width=True,
        hide_index=True
    )

    if st.button("💾 Save Execution Updates"):

        pid = st.session_state.project_id

        supabase.table("test_cases") \
            .delete() \
            .eq("project_id", pid) \
            .execute()

        records = st.session_state.current_df.to_dict("records")

        for r in records:
            r["project_id"] = pid
            r["case_id"] = r.pop("ID")
            r["scenario"] = r.pop("Scenario")
            r["expected"] = r.pop("Expected")
            r["status"] = r.pop("Status")
            r["severity"] = r.pop("Severity")
            r["priority"] = r.pop("Priority")
            r["module"] = r.pop("Module")
            r["assigned_to"] = r.pop("Assigned_To")
            r["actual_result"] = r.pop("Actual_Result")
            r["evidence_link"] = r.pop("Evidence_Link")

        supabase.table("test_cases").insert(records).execute()

        st.success("Execution Log Saved")

# ----------------------------------------------------
# TAB 3 - BUG CENTER
# ----------------------------------------------------
with tab3:

    st.subheader("🐞 Bug Center")

    df = st.session_state.current_df
    fails = df[df["Status"] == "Fail"]

    if fails.empty:
        st.info("No failed test cases.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"{bug['ID']} - {bug['Scenario']}"):

                module = st.text_input("Module", bug["Module"], key=f"mod{idx}")
                assigned = st.text_input("Assign To", bug["Assigned_To"], key=f"as{idx}")
                actual = st.text_area("Actual Result", bug["Actual_Result"], key=f"act{idx}")

                if st.button("Save Bug", key=f"save{idx}"):

                    supabase.table("bugs").insert({
                        "project_id": st.session_state.project_id,
                        "case_id": bug["ID"],
                        "scenario": bug["Scenario"],
                        "expected": bug["Expected"],
                        "actual_result": actual,
                        "severity": bug["Severity"],
                        "priority": bug["Priority"],
                        "module": module,
                        "assigned_to": assigned
                    }).execute()

                    st.success("Bug Saved")