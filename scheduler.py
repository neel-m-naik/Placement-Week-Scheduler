from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from models import Company, Student, Room, Interview, PriorityTier
from generator import generate_placement_dataset

DAY_START_MINUTES = 0        # 09:00 AM (0 minutes)
DAY_END_MINUTES = 480        # 05:00 PM (480 minutes = 8 working hours)
NUM_DAYS = 4                 # 4 placement days

@dataclass
class UnscheduledRecord:
    company_id: str
    student_id: str
    reason: str

@dataclass
class ScheduleResult:
    scheduled: List[Interview] = field(default_factory=list)
    unscheduled: List[UnscheduledRecord] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

class PlacementScheduler:
    def __init__(self, rooms: List[Room], companies: List[Company], students: List[Student]):
        self.rooms = rooms
        self.companies = {c.id: c for c in companies}
        self.students = {s.id: s for s in students}
        
        # Availability trackers: maps ID -> list of (day, start_time, end_time)
        self.student_busy: Dict[str, List[Tuple[int, int, int]]] = {s.id: [] for s in students}
        self.room_busy: Dict[str, List[Tuple[int, int, int]]] = {r.id: [] for r in rooms}
        # Tracks total booked minutes per room so allocation can prefer the
        # least-loaded room instead of always scanning R01, R02... in fixed
        # order, which used to cluster bookings and fragment capacity.
        self.room_load_minutes: Dict[str, int] = {r.id: 0 for r in rooms}
        # Panel busy map: (company_id, panel_index) -> list of (day, start_time, end_time)
        self.panel_busy: Dict[Tuple[str, int], List[Tuple[int, int, int]]] = {}
        for c in companies:
            for p in range(c.num_panels):
                self.panel_busy[(c.id, p)] = []

    def _is_busy(self, busy_list: List[Tuple[int, int, int]], day: int, start: int, end: int) -> bool:
        """Checks if a given interval overlaps with any existing booked slot."""
        for b_day, b_start, b_end in busy_list:
            if b_day == day:
                # Interval overlap condition
                if max(start, b_start) < min(end, b_end):
                    return True
        return False

    def _find_available_room(self, day: int, start: int, end: int) -> Optional[str]:
        """Finds the free room with the lowest total booked minutes so far.
        Preferring the least-loaded room (rather than always R01, R02...)
        spreads bookings more evenly across the day and reduces the
        fragmentation that used to strand slots later in the schedule."""
        candidates = [
            room for room in self.rooms
            if not self._is_busy(self.room_busy[room.id], day, start, end)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda r: self.room_load_minutes[r.id]).id

    def generate_schedule(self) -> ScheduleResult:
        result = ScheduleResult()
        
        # Step 1: Collect and prioritize all pending interview requests
        pending_requests = []
        for c_id, company in self.companies.items():
            for s_id in company.shortlisted_students:
                student = self.students[s_id]
                pending_requests.append({
                    "company_id": c_id,
                    "student_id": s_id,
                    "tier_value": company.tier.value,  # Tier 1 = 1 (highest priority)
                    "student_cgpa": student.cgpa,
                    "duration": company.duration_minutes
                })

        # Step 2: Sort requests (Tier 1 first -> Higher CGPA first)
        pending_requests.sort(
            key=lambda x: (x["tier_value"], -x["student_cgpa"])
        )

        interview_counter = 1

        # Step 3: Greedily assign slots
        for req in pending_requests:
            c_id = req["company_id"]
            s_id = req["student_id"]
            duration = req["duration"]
            company = self.companies[c_id]
            
            # Map company tier to preferred target days
            if company.tier == PriorityTier.TIER_1:
                target_days = [1, 2]
            elif company.tier == PriorityTier.TIER_2:
                target_days = [1, 2, 3]
            else:
                target_days = [2, 3, 4]

            scheduled = False
            failure_reasons = []

            for day in target_days:
                # Iterate in 15-minute slot increments
                for start_time in range(DAY_START_MINUTES, DAY_END_MINUTES - duration + 1, 15):
                    end_time = start_time + duration

                    # 1. Check Student availability
                    if self._is_busy(self.student_busy[s_id], day, start_time, end_time):
                        failure_reasons.append("STUDENT_BUSY")
                        continue

                    # 2. Check Company Panel availability
                    free_panel = None
                    for p in range(company.num_panels):
                        if not self._is_busy(self.panel_busy[(c_id, p)], day, start_time, end_time):
                            free_panel = p
                            break
                    
                    if free_panel is None:
                        failure_reasons.append("ALL_PANELS_OCCUPIED")
                        continue

                    # 3. Check Room availability
                    free_room_id = self._find_available_room(day, start_time, end_time)
                    if free_room_id is None:
                        failure_reasons.append("ROOMS_EXHAUSTED")
                        continue

                    # If all 3 are free, book the slot
                    self.student_busy[s_id].append((day, start_time, end_time))
                    self.panel_busy[(c_id, free_panel)].append((day, start_time, end_time))
                    self.room_busy[free_room_id].append((day, start_time, end_time))
                    self.room_load_minutes[free_room_id] += duration

                    interview = Interview(
                        id=f"INT_{interview_counter:04d}",
                        company_id=c_id,
                        student_id=s_id,
                        day=day,
                        start_time=start_time,
                        duration_minutes=duration,
                        room_id=free_room_id,
                        panel_id=free_panel,
                        status="SCHEDULED"
                    )
                    result.scheduled.append(interview)
                    interview_counter += 1
                    scheduled = True
                    break

                if scheduled:
                    break

            if not scheduled:
                # Determine primary bottleneck reason
                primary_reason = "SCHEDULE_CAPACITY_EXCEEDED"
                if "STUDENT_BUSY" in failure_reasons and "ALL_PANELS_OCCUPIED" not in failure_reasons:
                    primary_reason = "STUDENT_TIME_CONFLICT"
                elif "ROOMS_EXHAUSTED" in failure_reasons:
                    primary_reason = "ROOM_CAPACITY_EXHAUSTED"

                result.unscheduled.append(UnscheduledRecord(
                    company_id=c_id,
                    student_id=s_id,
                    reason=primary_reason
                ))

        # Step 4: Calculate Performance Metrics
        total_requests = len(pending_requests)
        total_scheduled = len(result.scheduled)
        total_room_capacity_mins = len(self.rooms) * NUM_DAYS * (DAY_END_MINUTES - DAY_START_MINUTES)
        total_room_booked_mins = sum(i.duration_minutes for i in result.scheduled)

        result.metrics = {
            "total_demand": total_requests,
            "total_scheduled": total_scheduled,
            "total_unscheduled": len(result.unscheduled),
            "match_rate_pct": round((total_scheduled / total_requests) * 100, 2) if total_requests else 0,
            "room_utilization_pct": round((total_room_booked_mins / total_room_capacity_mins) * 100, 2)
        }

        return result

if __name__ == "__main__":
    rooms, companies, students = generate_placement_dataset()
    scheduler = PlacementScheduler(rooms, companies, students)
    schedule_result = scheduler.generate_schedule()

    print("\n=== BASELINE SCHEDULER EXECUTION RESULTS ===")
    for k, v in schedule_result.metrics.items():
        print(f"• {k.replace('_', ' ').title()}: {v}")

    print(f"\nSample Scheduled Interviews (First 5):")
    for intvw in schedule_result.scheduled[:5]:
        start_hr = 9 + (intvw.start_time // 60)
        start_min = intvw.start_time % 60
        print(f"  [{intvw.id}] Day {intvw.day} @ {start_hr:02d}:{start_min:02d} | Company: {intvw.company_id} | Student: {intvw.student_id} | Room: {intvw.room_id} | Panel: {intvw.panel_id}")

    if schedule_result.unscheduled:
        print(f"\nSample Unscheduled Requests (First 3):")
        for unsched in schedule_result.unscheduled[:3]:
            print(f"  Company: {unsched.company_id} | Student: {unsched.student_id} | Reason: {unsched.reason}")