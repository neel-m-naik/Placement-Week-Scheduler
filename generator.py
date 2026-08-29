import random
import json
from dataclasses import asdict
from models import Company, Student, Room, PriorityTier

def generate_placement_dataset(seed: int = 42):
    random.seed(seed)
    
    # 1. Generate 20 Interview Rooms
    rooms = [Room(id=f"R{i+1:02d}", name=f"Room {100 + i + 1}") for i in range(20)] #
    
    # 2. Generate 35 Companies across 3 Tiers
    companies = []
    
    # 5 Tier-1 Companies (Super Dream: High CGPA cutoff, 45m interviews, 2-4 panels)
    for i in range(1, 6):
        companies.append(Company(
            id=f"C{i:02d}",
            name=f"DreamCorp_{i}",
            tier=PriorityTier.TIER_1,
            cgpa_cutoff=round(random.uniform(8.0, 8.7), 2),
            duration_minutes=45,
            num_panels=random.randint(2, 4)
        ))
        
    # 12 Tier-2 Companies (Core/Product: Moderate cutoff, 30m interviews, 3-6 panels)
    for i in range(6, 18):
        companies.append(Company(
            id=f"C{i:02d}",
            name=f"CoreTech_{i}",
            tier=PriorityTier.TIER_2,
            cgpa_cutoff=round(random.uniform(7.0, 7.8), 2),
            duration_minutes=30,
            num_panels=random.randint(3, 6)
        ))
        
    # 18 Tier-3 Companies (Mass Recruiters: Lower cutoff, 20m interviews, 6-10 panels)
    for i in range(18, 36):
        companies.append(Company(
            id=f"C{i:02d}",
            name=f"MassRecruiter_{i}",
            tier=PriorityTier.TIER_3,
            cgpa_cutoff=round(random.uniform(6.0, 6.8), 2),
            duration_minutes=20,
            num_panels=random.randint(6, 10)
        )) #

    # 3. Generate 800 Students
    branches = ["CSE", "ISE", "ECE", "EEE", "MECH", "CIVIL"]
    students = []
    
    for i in range(1, 801): #[cite: 1]
        # Normal distribution for CGPA: Mean=7.5, StdDev=1.0, clamped [5.0, 10.0]
        raw_cgpa = random.gauss(7.5, 1.0)
        cgpa = round(max(5.0, min(10.0, raw_cgpa)), 2)
        
        students.append(Student(
            id=f"S{i:03d}",
            name=f"Student_{i}",
            cgpa=cgpa,
            branch=random.choice(branches)
        ))

    # 4. Realistic Shortlisting Logic (Simulating heavy schedule overlap)
    #
    # Sized against actual shared room-minute capacity so total demand is
    # oversubscribed enough to be realistic (there SHOULD be some contention
    # and unscheduled leftovers) without being mathematically impossible.
    # Total capacity = 20 rooms x 480 min/day x 4 days = 38,400 room-minutes.
    # Target ~1.15-1.3x of that in total demand, split across tiers roughly
    # proportional to their day-window access (Tier-1: days 1-2, Tier-2:
    # days 1-3, Tier-3: days 2-4) so no single tier is structurally starved.
    for company in companies:
        eligible_students = [s for s in students if s.cgpa >= company.cgpa_cutoff]
        
        if company.tier == PriorityTier.TIER_1:
            # Shortlists top 30-50 eligible candidates
            sample_size = min(len(eligible_students), random.randint(30, 50))
            # Heavily weight toward the highest CGPA students
            eligible_students.sort(key=lambda s: s.cgpa, reverse=True)
            shortlist = eligible_students[:sample_size]
        elif company.tier == PriorityTier.TIER_2:
            # Shortlists 40-70 candidates (12 companies x ~55 avg x 30min
            # = ~19,800 room-min demand, sharing days 1-3 with Tier-1/Tier-3)
            sample_size = min(len(eligible_students), random.randint(40, 70))
            shortlist = random.sample(eligible_students, sample_size)
        else:
            # Tier-3 / Mass recruiters shortlist 35-65 candidates.
            # 18 companies x ~50 avg x 20min = ~18,000 room-min demand,
            # sharing days 2-4 with Tier-1 (day 2 only) and Tier-2 (days 2-3).
            sample_size = min(len(eligible_students), random.randint(35, 65))
            shortlist = random.sample(eligible_students, sample_size)
            
        for student in shortlist:
            company.shortlisted_students.append(student.id)
            student.shortlisted_by.append(company.id)

    return rooms, companies, students

if __name__ == "__main__":
    rooms, companies, students = generate_placement_dataset()
    
    # Summary Verification
    total_shortlists = sum(len(c.shortlisted_students) for c in companies)
    contested_students = [s for s in students if len(s.shortlisted_by) >= 5]
    
    print("=== DATASET GENERATION SUMMARY ===")
    print(f"Total Rooms: {len(rooms)}") #[cite: 1]
    print(f"Total Companies: {len(companies)}") #[cite: 1]
    print(f"Total Students: {len(students)}") #[cite: 1]
    print(f"Total Interview Demands: {total_shortlists}")
    print(f"Heavily Contested Students (5+ Shortlists): {len(contested_students)}")
    print(f"Max Shortlists for a Single Student: {max(len(s.shortlisted_by) for s in students)}")