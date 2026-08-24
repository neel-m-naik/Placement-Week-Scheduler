import streamlit as st
import pandas as pd
from generator import generate_placement_dataset
from scheduler import PlacementScheduler
from replanner import PlacementReplanner

# Set Page Config
st.set_page_config(page_title="Placement Week Scheduler", layout="wide", page_icon="🎓")

# Custom Styling for Dashboard
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; border-radius: 8px; padding: 15px; border-left: 5px solid #1E88E5; }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State
if "rooms" not in st.session_state:
    rooms, companies, students = generate_placement_dataset()
    st.session_state.rooms = rooms
    st.session_state.companies = companies
    st.session_state.students = students
    
    scheduler = PlacementScheduler(rooms, companies, students)
    schedule_result = scheduler.generate_schedule()
    
    st.session_state.schedule = schedule_result.scheduled
    st.session_state.unscheduled = schedule_result.unscheduled
    st.session_state.metrics = schedule_result.metrics
    st.session_state.diff_history = []
    st.session_state.last_churn = 0

# Helper to format minute timestamps to HH:MM format
def format_time(start_mins: int) -> str:
    hr = 9 + (start_mins // 60)
    mn = start_mins % 60
    return f"{hr:02d}:{mn:02d}"

# Sidebar Controls
st.sidebar.title("🎛️ Control Panel")

if st.sidebar.button("🔄 Regenerate Base Dataset & Schedule", use_container_width=True):
    rooms, companies, students = generate_placement_dataset()
    st.session_state.rooms = rooms
    st.session_state.companies = companies
    st.session_state.students = students
    scheduler = PlacementScheduler(rooms, companies, students)
    schedule_result = scheduler.generate_schedule()
    st.session_state.schedule = schedule_result.scheduled
    st.session_state.unscheduled = schedule_result.unscheduled
    st.session_state.metrics = schedule_result.metrics
    st.session_state.diff_history = []
    st.session_state.last_churn = 0
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Live Disruption Simulator")

# Disruption Option 1: Company Delay
with st.sidebar.expander("⏱️ Company Late Arrival"):
    selected_comp = st.selectbox("Company", [c.id for c in st.session_state.companies], index=0)
    delay_hours = st.slider("Delay (Hours)", min_value=1, max_value=4, value=2)
    current_day = st.selectbox("Current Day", [1, 2, 3, 4], index=0)
    
    if st.button("Apply Company Delay", use_container_width=True):
        replanner = PlacementReplanner(
            st.session_state.rooms, 
            st.session_state.companies, 
            st.session_state.students, 
            st.session_state.schedule
        )
        res = replanner.handle_company_delay(selected_comp, delay_hours * 60, current_day=current_day, current_time=0)
        st.session_state.schedule = res.updated_schedule
        st.session_state.diff_history = res.diff
        st.session_state.last_churn = res.churn_count
        st.rerun()

# Disruption Option 2: Student Withdrawal
with st.sidebar.expander("🚪 Student Withdrawal"):
    selected_student = st.selectbox("Student ID", [s.id for s in st.session_state.students], index=4)
    if st.button("Apply Student Withdrawal", use_container_width=True):
        replanner = PlacementReplanner(
            st.session_state.rooms, 
            st.session_state.companies, 
            st.session_state.students, 
            st.session_state.schedule
        )
        res = replanner.handle_student_withdrawal(selected_student, current_day=1, current_time=0)
        st.session_state.schedule = res.updated_schedule
        st.session_state.diff_history = res.diff
        st.session_state.last_churn = res.churn_count
        st.rerun()

# Top KPI Metric Cards
st.title("Campus Placement Week Scheduling Engine")
col1, col2, col3, col4 = st.columns(4)

total_interviews = len([iv for iv in st.session_state.schedule if iv.status == "SCHEDULED"])
match_rate = st.session_state.metrics.get("match_rate_pct", 0.0)
room_util = st.session_state.metrics.get("room_utilization_pct", 0.0)

col1.metric("Confirmed Interviews", f"{total_interviews}")
col2.metric("Overall Match Rate", f"{match_rate}%")
col3.metric("Room Utilization", f"{room_util}%")
col4.metric("Last Disruption Churn", f"{st.session_state.last_churn} slots", delta_color="inverse")

st.markdown("---")

# Main Content Tabs
tab1, tab2, tab3 = st.tabs(["📅 Master Schedule", "🔄 Replan & Disruption Diff", "⚠️ Diagnostic Log"])

with tab1:
    st.subheader("Master Interview Timetable")
    
    f_col1, f_col2 = st.columns(2)
    selected_day = f_col1.selectbox("Filter by Day", ["All", 1, 2, 3, 4], index=0)
    status_filter = f_col2.selectbox("Filter by Status", ["All", "SCHEDULED", "PENDING_RESCHEDULE", "CANCELLED", "DEFERRED_NEXT_DAY"], index=0)

    # Build DataFrame for visualization
    records = []
    for iv in st.session_state.schedule:
        if selected_day != "All" and iv.day != selected_day:
            continue
        if status_filter != "All" and iv.status != status_filter:
            continue
            
        records.append({
            "Interview ID": iv.id,
            "Day": f"Day {iv.day}",
            "Time Window": f"{format_time(iv.start_time)} - {format_time(iv.start_time + iv.duration_minutes)}",
            "Company": iv.company_id,
            "Student": iv.student_id,
            "Room": iv.room_id if iv.room_id else "N/A",
            "Panel": f"Panel {iv.panel_id}" if iv.panel_id is not None else "N/A",
            "Status": iv.status
        })

    if records:
        df_schedule = pd.DataFrame(records)
        st.dataframe(df_schedule, use_container_width=True, hide_index=True)
    else:
        st.info("No interviews match the selected filters.")

with tab2:
    st.subheader("Disruption Impact Changelog (Diff Output)")
    if st.session_state.diff_history:
        diff_data = []
        for d in st.session_state.diff_history:
            diff_data.append({
                "Interview ID": d.interview_id,
                "Student": d.student_id,
                "Company": d.company_id,
                "Action Taken": d.action,
                "Original Allocation": d.old_slot,
                "New Allocation": d.new_slot if d.new_slot else "Cancelled / Deferred",
                "Parties to Notify": ", ".join(d.affected_parties)
            })
        st.dataframe(pd.DataFrame(diff_data), use_container_width=True, hide_index=True)
    else:
        st.success("No active disruptions. Schedule is running normally.")

with tab3:
    st.subheader("Unscheduled Interview Diagnostic Log")
    st.caption("Detailed reasons why certain interview demands could not be scheduled initially.")
    
    if st.session_state.unscheduled:
        unsched_records = [{
            "Company": u.company_id,
            "Student": u.student_id,
            "Failure Bottleneck": u.reason
        } for u in st.session_state.unscheduled]
        st.dataframe(pd.DataFrame(unsched_records), use_container_width=True, hide_index=True)
    else:
        st.success("100% of candidate demands were scheduled without conflicts!")

# Disruption Option 3: Defense Combo Stress-Test
with st.sidebar.expander("🚨 Live Defense Stress Test"):
    st.caption("Simulates: Day-1 recruiter 3h late + 15 student withdrawals simultaneously.")
    if st.button("Trigger Compound Crisis", use_container_width=True):
        replanner = PlacementReplanner(
            st.session_state.rooms, 
            st.session_state.companies, 
            st.session_state.students, 
            st.session_state.schedule
        )
        # 1. Company delay (Tier-1 DreamCorp_1 is 3h late)
        res1 = replanner.handle_company_delay("C01", delay_minutes=180, current_day=1, current_time=0)
        
        # 2. 15 students withdraw simultaneously
        withdrawn_ids = [f"S{i:03d}" for i in range(1, 16)]
        all_diffs = list(res1.diff)
        for s_id in withdrawn_ids:
            res_w = replanner.handle_student_withdrawal(s_id, current_day=1, current_time=0)
            all_diffs.extend(res_w.diff)
            
        st.session_state.schedule = replanner.schedule
        st.session_state.diff_history = all_diffs
        st.session_state.last_churn = len(all_diffs)
        st.rerun()