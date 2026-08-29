# Placement Week Dynamic Scheduler

An automated, conflict-free scheduling and real-time replanning engine designed to coordinate 35 companies, 800 students, 4 days, and 20 rooms under high contention and live disruptions.

## System Architecture

- **`models.py`**: Data schemas for companies (tiers, cutoffs, durations, panels), students, rooms, and interview slots.
- **`generator.py`**: Synthetic data generator modeling realistic, skewed student shortlists and placement contention[cite: 1].
- **`scheduler.py`**: Priority-based greedy allocation engine enforcing zero double-booking and tracking explicit bottleneck reasons[cite: 1].
- **`replanner.py`**: Low-churn disruption engine handling late arrivals, room failures, panel drops, and withdrawals with structured diff logs[cite: 1].
- **`app.py`**: Interactive Streamlit coordinator dashboard for live schedule monitoring and one-click disruption simulation[cite: 1].
- **`test_simulation.py`**: Automated CLI test suite validating mathematical non-overlap constraints.

## Key Design Decisions & Trade-Offs

### 1. What Defines a "Good" Schedule?
- **High Tier-1 Match Rate (≥ 95%):** Prioritizes top-tier companies and high-CGPA candidates on Days 1 and 2[cite: 1].
- **Controlled Room Utilization (70% – 85%):** Maintains a buffer of empty rooms to absorb delays and overruns without causing cascading failures.
- **Low Replan Churn:** When a disruption occurs, minimal appointments are shifted to avoid campus-wide confusion[cite: 1].

### 2. Constraint Bending Order
When the schedule becomes over-constrained, soft constraints bend in strict sequence:
1. **Room Relocation:** Change the room assignment while keeping the exact same time slot.
2. **Buffer Compression:** Reduce gap buffers between interviews.
3. **Day Deferral:** Move lower-tier mass recruiter interviews to later placement days.
*Hard Constraints (never placing a student, panel, or room in two places at once) never bend[cite: 1].*

### 3. Reshuffle Limits & Coordinator Authority
Reshuffling is strictly bounded to the blast radius of the disruption (e.g., only moving future slots of the delayed company)[cite: 1]. The system computes the optimal low-churn solution automatically, but leaves final approval to the coordinator[cite: 1].

## Installation & Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Coordinator Dashboard
```bash
streamlit run app.py
```

### 3. Run the Automated CLI Test Suite
```bash
python test_simulation.py
```