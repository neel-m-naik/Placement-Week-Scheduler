from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class PriorityTier(Enum):
    TIER_1 = 1  # Super Dream / High CTC (Day 1)
    TIER_2 = 2  # Dream / Core
    TIER_3 = 3  # Mass Recruiters

@dataclass
class Company:
    id: str
    name: str
    tier: PriorityTier
    cgpa_cutoff: float
    duration_minutes: int     # e.g., 45, 30, or 20 minutes
    num_panels: int           # Number of parallel interview panels
    shortlisted_students: List[str] = field(default_factory=list)

@dataclass
class Student:
    id: str
    name: str
    cgpa: float
    branch: str
    shortlisted_by: List[str] = field(default_factory=list)

@dataclass
class Room:
    id: str
    name: str

@dataclass
class Interview:
    id: str
    company_id: str
    student_id: str
    day: int                  # Day 1 to 4
    start_time: int           # Minutes from start of day (e.g., 0 = 09:00 AM, 60 = 10:00 AM)
    duration_minutes: int
    room_id: Optional[str] = None
    panel_id: Optional[int] = None
    status: str = "SCHEDULED" # SCHEDULED, CANCELLED, RESCHEDULED