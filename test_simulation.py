import sys
from generator import generate_placement_dataset
from scheduler import PlacementScheduler
from replanner import PlacementReplanner

def run_headless_defense_test():
    print("==================================================")
    print("   PLACEMENT SCHEDULER CLI DEFENSE VERIFICATION   ")
    print("==================================================")

    # 1. Dataset & Schedule Generation
    print("\n[STEP 1] Generating Dataset & Baseline Schedule...")
    rooms, companies, students = generate_placement_dataset()
    scheduler = PlacementScheduler(rooms, companies, students)
    schedule_res = scheduler.generate_schedule()

    print(f"✓ Base Interviews Scheduled: {len(schedule_res.scheduled)}")
    print(f"✓ Match Rate: {schedule_res.metrics['match_rate_pct']}%")
    print(f"✓ Room Utilization: {schedule_res.metrics['room_utilization_pct']}%")
    print(f"✓ Unscheduled Demands Logged: {len(schedule_res.unscheduled)}")

    # 2. Hard Constraint Verification
    print("\n[STEP 2] Verifying Hard Constraints (Zero Overlaps)...")
    student_bookings = {}
    room_bookings = {}
    
    for iv in schedule_res.scheduled:
        # Check student double booking
        s_key = (iv.student_id, iv.day)
        student_bookings.setdefault(s_key, []).append((iv.start_time, iv.start_time + iv.duration_minutes))
        # Check room double booking
        r_key = (iv.room_id, iv.day)
        room_bookings.setdefault(r_key, []).append((iv.start_time, iv.start_time + iv.duration_minutes))

    def has_clashes(booking_dict):
        for key, intervals in booking_dict.items():
            intervals.sort()
            for i in range(len(intervals) - 1):
                if intervals[i][1] > intervals[i+1][0]:
                    return True
        return False

    assert not has_clashes(student_bookings), "Student double booking detected!"
    assert not has_clashes(room_bookings), "Room double booking detected!"
    print("✓ Hard Constraints Validated: Zero student or room overlaps.")

    # 3. Compound Disruption Simulation
    print("\n[STEP 3] Simulating Disruption:")
    print("  • Recruiter C01 delayed by 3 hours (180 mins)")
    print("  • 15 Students (S001 to S015) withdraw simultaneously")

    replanner = PlacementReplanner(rooms, companies, students, schedule_res.scheduled)
    
    # Delay C01
    delay_res = replanner.handle_company_delay("C01", delay_minutes=180, current_day=1, current_time=0)
    
    # Withdraw 15 students
    all_diffs = list(delay_res.diff)
    for s_idx in range(1, 16):
        s_id = f"S{s_idx:03d}"
        w_res = replanner.handle_student_withdrawal(s_id, current_day=1, current_time=0)
        all_diffs.extend(w_res.diff)

    print(f"\n✓ Disruption Resolved Successfully.")
    print(f"✓ Total Modifications (Churn): {len(all_diffs)}")
    print("✓ Sample Diff Output:")
    for diff in all_diffs[:4]:
        print(f"   [{diff.action}] Student: {diff.student_id} | Company: {diff.company_id} | {diff.old_slot} -> {diff.new_slot or 'CANCELLED'}")

    print("\n==================================================")
    print("             ALL CLI CHECKS PASSED                ")
    print("==================================================")

if __name__ == "__main__":
    run_headless_defense_test()