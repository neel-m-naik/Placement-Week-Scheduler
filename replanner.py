from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from models import Company, Student, Room, Interview
from scheduler import PlacementScheduler, DAY_START_MINUTES, DAY_END_MINUTES, NUM_DAYS
from generator import generate_placement_dataset

@dataclass
class ScheduleDiffItem:
    interview_id: str
    student_id: str
    company_id: str
    action: str               # "MOVED_TIME", "RELOCATED_ROOM", "PANEL_REASSIGNED", "CANCELLED", "DEFERRED"
    old_slot: Optional[str]
    new_slot: Optional[str]
    affected_parties: List[str]

@dataclass
class ReplanResult:
    updated_schedule: List[Interview]
    diff: List[ScheduleDiffItem]
    churn_count: int
    unresolved_count: int

class PlacementReplanner:
    def __init__(self, rooms: List[Room], companies: List[Company], students: List[Student], current_schedule: List[Interview]):
        self.rooms = rooms
        self.companies = {c.id: c for c in companies}
        self.students = {s.id: s for s in students}
        self.schedule = [Interview(**vars(i)) for i in current_schedule]

    def _format_slot(self, day: int, start_min: int, room_id: Optional[str], panel_id: Optional[int]) -> str:
        hr = 9 + (start_min // 60)
        mn = start_min % 60
        return f"Day {day} {hr:02d}:{mn:02d} (Room: {room_id}, Panel: {panel_id})"

    def _rebuild_occupancy(self, schedule: List[Interview]):
        student_busy = {s: [] for s in self.students}
        room_busy = {r.id: [] for r in self.rooms}
        panel_busy = {}
        for c in self.companies.values():
            for p in range(c.num_panels):
                panel_busy[(c.id, p)] = []

        for iv in schedule:
            if iv.status != "SCHEDULED":
                continue
            student_busy[iv.student_id].append((iv.day, iv.start_time, iv.start_time + iv.duration_minutes))
            if iv.room_id:
                room_busy[iv.room_id].append((iv.day, iv.start_time, iv.start_time + iv.duration_minutes))
            if iv.panel_id is not None:
                panel_busy[(iv.company_id, iv.panel_id)].append((iv.day, iv.start_time, iv.start_time + iv.duration_minutes))

        return student_busy, room_busy, panel_busy

    def handle_company_delay(self, company_id: str, delay_minutes: int, current_day: int, current_time: int) -> ReplanResult:
        diff: List[ScheduleDiffItem] = []
        affected = [
            iv for iv in self.schedule 
            if iv.company_id == company_id and iv.day == current_day and iv.start_time >= current_time and iv.status == "SCHEDULED"
        ]

        # Preserve each interview's original relative ordering so the earliest
        # -scheduled interviews still get first pick of the post-delay slots
        # (keeps churn low and avoids arbitrarily reordering the queue).
        affected.sort(key=lambda iv: iv.start_time)

        for iv in affected:
            iv.status = "PENDING_RESCHEDULE"

        student_busy, room_busy, panel_busy = self._rebuild_occupancy(self.schedule)
        comp = self.companies[company_id]

        for iv in affected:
            old_slot = self._format_slot(iv.day, iv.start_time, iv.room_id, iv.panel_id)
            rescheduled = False

            # Each interview shifts by delay_minutes from its OWN original
            # start time (not a single global floor), so a 9:00 interview
            # delayed 60min searches from 10:00, and an 11:15 interview
            # delayed 60min searches from 12:15 — never earlier than before.
            iv_effective_start = max(current_time, iv.start_time + delay_minutes)

            for start_t in range(iv_effective_start, DAY_END_MINUTES - iv.duration_minutes + 1, 15):
                end_t = start_t + iv.duration_minutes

                # Check student free
                if any(b_d == current_day and max(start_t, bs) < min(end_t, be) for b_d, bs, be in student_busy[iv.student_id]):
                    continue

                # Check panel free
                free_panel = next((p for p in range(comp.num_panels) if not any(b_d == current_day and max(start_t, bs) < min(end_t, be) for b_d, bs, be in panel_busy[(company_id, p)])), None)
                if free_panel is None:
                    continue

                # Check room free
                free_room = next((r.id for r in self.rooms if not any(b_d == current_day and max(start_t, bs) < min(end_t, be) for b_d, bs, be in room_busy[r.id])), None)
                if free_room is None:
                    continue

                iv.start_time = start_t
                iv.room_id = free_room
                iv.panel_id = free_panel
                iv.status = "SCHEDULED"

                student_busy[iv.student_id].append((current_day, start_t, end_t))
                panel_busy[(company_id, free_panel)].append((current_day, start_t, end_t))
                room_busy[free_room].append((current_day, start_t, end_t))

                diff.append(ScheduleDiffItem(
                    interview_id=iv.id,
                    student_id=iv.student_id,
                    company_id=company_id,
                    action="MOVED_TIME",
                    old_slot=old_slot,
                    new_slot=self._format_slot(current_day, start_t, free_room, free_panel),
                    affected_parties=[f"Student {iv.student_id}", f"Company {company_id}"]
                ))
                rescheduled = True
                break

            if not rescheduled:
                iv.status = "DEFERRED_NEXT_DAY"
                diff.append(ScheduleDiffItem(
                    interview_id=iv.id,
                    student_id=iv.student_id,
                    company_id=company_id,
                    action="DEFERRED",
                    old_slot=old_slot,
                    new_slot=None,
                    affected_parties=[f"Student {iv.student_id}", "Coordinator"]
                ))

        churn = len([d for d in diff if d.action in ("MOVED_TIME", "DEFERRED")])
        unresolved = len([d for d in diff if d.action == "DEFERRED"])
        return ReplanResult(self.schedule, diff, churn, unresolved)

    def handle_student_withdrawal(self, student_id: str, current_day: int, current_time: int) -> ReplanResult:
        diff: List[ScheduleDiffItem] = []
        for iv in self.schedule:
            is_future = (iv.day > current_day) or (iv.day == current_day and iv.start_time >= current_time)
            if iv.student_id == student_id and is_future and iv.status == "SCHEDULED":
                old_desc = self._format_slot(iv.day, iv.start_time, iv.room_id, iv.panel_id)
                iv.status = "CANCELLED"
                diff.append(ScheduleDiffItem(
                    interview_id=iv.id,
                    student_id=student_id,
                    company_id=iv.company_id,
                    action="CANCELLED",
                    old_slot=old_desc,
                    new_slot=None,
                    affected_parties=[f"Company {iv.company_id} Panel {iv.panel_id}"]
                ))
        return ReplanResult(self.schedule, diff, len(diff), 0)


# ==========================================
# THIS PART RUNS WHEN YOU EXECUTE THE FILE
# ==========================================
if __name__ == "__main__":
    print("1. Generating initial data and schedule...")
    rooms, companies, students = generate_placement_dataset()
    scheduler = PlacementScheduler(rooms, companies, students)
    base_schedule = scheduler.generate_schedule()
    print(f"-> Baseline scheduled: {len(base_schedule.scheduled)} interviews.\n")

    replanner = PlacementReplanner(rooms, companies, students, base_schedule.scheduled)

    # Simulation Test A: Company C01 is 2 hours (120 min) late on Day 1 at 9:00 AM
    print("2. Simulating disruption: Company C01 arrives 2 hours late...")
    delay_res = replanner.handle_company_delay(company_id="C01", delay_minutes=120, current_day=1, current_time=0)
    print(f"-> Total Rescheduled (Churn): {delay_res.churn_count}")
    print(f"-> Unresolved (Deferred to Day 2): {delay_res.unresolved_count}")
    print("-> Changeset preview (first 2 changes):")
    for item in delay_res.diff[:2]:
        print(f"   * [{item.action}] Student {item.student_id} | Old: {item.old_slot} -> New: {item.new_slot}")

    # Simulation Test B: Student S005 gets an offer and drops out of all other interviews
    print("\n3. Simulating disruption: Student S005 placed elsewhere and withdraws...")
    withdraw_res = replanner.handle_student_withdrawal(student_id="S005", current_day=1, current_time=60)
    print(f"-> Total slots cancelled and freed up: {withdraw_res.churn_count}")
    for item in withdraw_res.diff:
        print(f"   * [{item.action}] Cancelled slot at {item.old_slot}")