import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Senior QA Operating System", layout="wide")

# --------------------------------------------------
# SUPABASE INIT
# --------------------------------------------------
@st.cache_resource
def init_connection():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = init_connection()

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def get_projects():
    return supabase.table("projects").select("*").execute().data or []

def create_project(name):
    supabase.table("projects").insert({"name": name}).execute()

def get_project_id(name):
    res = supabase.table("projects").select("id").eq("name", name).execute()
    return res.data[0]["id"]

def save_audit(pid, rewrite, feature_table, strategy, doubts):
    supabase.table("strategies").upsert({
        "project_id": pid,
        "rewrite": rewrite,
        "feature_table": feature_table,
        "strategy_text": strategy,
        "doubts": doubts
    }).execute()

def load_audit(pid):
    res = supabase.table("strategies").select("*").eq("project_id", pid).execute()
    return res.data[0] if res.data else None

def load_testcases(pid):
    res = supabase.table("test_cases").select("*").eq("project_id", pid).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def save_testcases(pid, df):
    supabase.table("test_cases").delete().eq("project_id", pid).execute()

    records = df.to_dict("records")
    for r in records:
        r["project_id"] = pid
    if records:
        supabase.table("test_cases").insert(records).execute()

def bug_exists(pid, case_id):
    res = supabase.table("bugs").select("id").eq("project_id", pid).eq("case_id", case_id).execute()
    return bool(res.data)

def create_bug(pid, row):
    supabase.table("bugs").insert({
        "project_id": pid,
        "case_id": row["case_id"],
        "title": f"Bug from: {row['scenario']}",
        "description": f"Auto-generated from failed test case.\n\nExpected:\n{row['expected']}",
        "assigned_to": row["assigned_to"],
        "severity": row["severity"],
        "priority": row["priority"],
        "created_at": datetime.now().isoformat()
    }).execute()

def load_bugs(pid):
    res = supabase.table("bugs").select("*").eq("project_id", pid).execute()
    return res.data or []

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.title("📂 Projects")

    projects = get_projects()
    names = [p["name"] for p in projects]

    selected = st.selectbox("Switch Project", names + ["+ New Project"])

    if selected == "+ New Project":
        new_name = st.text_input("New Project Name")
        if st.button("Create"):
            create_project(new_name)
            st.rerun()
    else:
        pid = get_project_id(selected)
        st.session_state.project_id = pid

# --------------------------------------------------
# MAIN
# --------------------------------------------------
if "project_id" not in st.session_state:
    st.info("Create or Select a project to begin.")
    st.stop()

pid = st.session_state.project_id

tab1, tab2, tab3 = st.tabs([
    "🏗️ Senior QA Audit & Strategy",
    "✅ Execution Log",
    "🐞 Bug Center"
])

# --------------------------------------------------
# TAB 1 - AUDIT (NO TEST CASE DISPLAY HERE)
# --------------------------------------------------
with tab1:
    st.subheader("Senior QA Audit & Strategy")

    audit = load_audit(pid)

    rewrite = st.text_area("1️⃣ REWRITE", audit["rewrite"] if audit else "", height=150)
    feature_table = st.text_area("2️⃣ FEATURE TABLE", audit["feature_table"] if audit else "", height=150)
    strategy = st.text_area("3️⃣ STRATEGY", audit["strategy_text"] if audit else "", height=150)
    doubts = st.text_area("4️⃣ DOUBTS", audit["doubts"] if audit else "", height=150)

    if st.button("💾 Save Audit"):
        save_audit(pid, rewrite, feature_table, strategy, doubts)
        st.success("Saved Successfully")

# --------------------------------------------------
# TAB 2 - EXECUTION LOG WITH DROPDOWN
# --------------------------------------------------
with tab2:
    st.subheader("Execution Log")

    df = load_testcases(pid)

    if df.empty:
        st.info("No test cases available.")
    else:
        df["status"] = df["status"].fillna("Pending")
        df["assigned_to"] = df["assigned_to"].fillna("")

        edited_df = st.data_editor(
            df,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Pass", "Fail"]
                )
            },
            use_container_width=True
        )

        if st.button("💾 Save Execution Updates"):
            save_testcases(pid, edited_df)

            # Auto bug generation for failed cases
            for _, row in edited_df.iterrows():
                if row["status"] == "Fail":
                    if not bug_exists(pid, row["case_id"]):
                        create_bug(pid, row)

            st.success("Execution Log Updated")
            st.rerun()

# --------------------------------------------------
# TAB 3 - BUG CENTER
# --------------------------------------------------
with tab3:
    st.subheader("Bug Center")

    bugs = load_bugs(pid)

    if not bugs:
        st.info("No Bugs Yet.")
    else:
        for bug in bugs:
            with st.expander(bug["title"]):
                st.write(f"**Assigned To:** {bug['assigned_to']}")
                st.write(f"**Severity:** {bug['severity']}")
                st.write(f"**Priority:** {bug['priority']}")
                st.write(f"**Created At:** {bug['created_at']}")
                st.text_area(
                    "Description",
                    bug["description"],
                    key=f"bug_{bug['id']}"
                )