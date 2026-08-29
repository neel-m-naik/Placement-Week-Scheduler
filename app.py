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
tab1, tab2, tab3, tab4 = st.tabs(["📅 Master Schedule", "🔄 Replan & Disruption Diff", "⚠️ Diagnostic Log", "📊 Capacity Math"])

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

with tab4:
    st.subheader("Demand vs. Room-Minute Capacity, by Tier")
    st.caption(
        "Match rate is fundamentally bounded by physical room-minutes, not just algorithm quality. "
        "This shows why each tier lands where it does."
    )

    from models import PriorityTier
    ROOM_CAPACITY_PER_DAY = len(st.session_state.rooms) * 480  # rooms x 8hr day in minutes

    tier_day_windows = {
        PriorityTier.TIER_1: [1, 2],
        PriorityTier.TIER_2: [1, 2, 3],
        PriorityTier.TIER_3: [2, 3, 4],
    }
    tier_labels = {
        PriorityTier.TIER_1: "Tier 1 (Super Dream)",
        PriorityTier.TIER_2: "Tier 2 (Core/Product)",
        PriorityTier.TIER_3: "Tier 3 (Mass Recruiters)",
    }

    scheduled_by_tier = {t: 0 for t in PriorityTier}
    demand_by_tier = {t: 0 for t in PriorityTier}
    demand_mins_by_tier = {t: 0 for t in PriorityTier}
    comp_tier_map = {c.id: c.tier for c in st.session_state.companies}
    comp_dur_map = {c.id: c.duration_minutes for c in st.session_state.companies}

    for c in st.session_state.companies:
        demand_by_tier[c.tier] += len(c.shortlisted_students)
        demand_mins_by_tier[c.tier] += len(c.shortlisted_students) * c.duration_minutes

    for iv in st.session_state.schedule:
        if iv.status == "SCHEDULED":
            scheduled_by_tier[comp_tier_map[iv.company_id]] += 1

    capacity_rows = []
    for t in PriorityTier:
        window_days = tier_day_windows[t]
        # NOTE: this is each tier's own day-window capacity, not accounting
        # for the fact multiple tiers overlap on shared days (e.g. Tier-2
        # and Tier-3 both compete for days 2-3) — actual effective capacity
        # per tier is lower than this number whenever days are shared.
        own_window_capacity = ROOM_CAPACITY_PER_DAY * len(window_days)
        demanded = demand_by_tier[t]
        matched = scheduled_by_tier[t]
        capacity_rows.append({
            "Tier": tier_labels[t],
            "Day Window": ", ".join(f"Day {d}" for d in window_days),
            "Requests (demand)": demanded,
            "Demand (room-min)": demand_mins_by_tier[t],
            "Own-Window Capacity (room-min)": own_window_capacity,
            "Actually Matched": matched,
            "Match Rate": f"{round(100 * matched / demanded, 1) if demanded else 0}%",
        })

    st.dataframe(pd.DataFrame(capacity_rows), use_container_width=True, hide_index=True)

    st.info(
        "Days 2 and 3 are shared between Tier-2 and Tier-3 (and Day 2 also serves Tier-1), "
        "so a tier's real available capacity is lower than its 'own-window' number whenever "
        "higher-priority tiers are also drawing on the same days. This is why Tier-3 "
        "structurally has the lowest match rate even with a well-tuned scheduler — "
        "it sits last in priority order on the most contested days."
    )

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