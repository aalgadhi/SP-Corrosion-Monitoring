"""
GasGuard AI — Synthetic Corrosion Dataset Generator v2
Team M056 — Senior Design Project II (Term 252)

Pipe Material: Carbon Steel Schedule 40 (ASTM A106 Gr.B)
  - Nominal size: 4" NPS
  - Wall thickness (T0): 6.02 mm
  - Min. allowable thickness (Tc): 3.0 mm (ASME B31.3 + safety factor)

RUL Equation:
  RUL = (T(t) - Tc) / Corrosion_Rate
  Where:
    T(t)  = current wall thickness at time t (mm)
    Tc    = minimum allowable wall thickness (mm)
    CR    = corrosion rate (mm/day)

Corrosion Rate Model (simplified de Waard–Milliams inspired):
  CR depends on H₂S, CO₂ partial pressure, temperature, and O₂
  Higher H₂S → sour corrosion acceleration
  Higher CO₂ → sweet (carbonic acid) corrosion
  Higher temp → faster kinetics (up to ~120°C)
  O₂ presence → accelerates oxidation

Output columns:
  segment_id, timestep, H2S_ppm, CO_ppm, CO2_ppm, CH4_LEL_pct,
  O2_vol_pct, flow_rate, temperature_C, pressure_bar,
  Corrosion_Rate_mm_per_day, RUL_days
"""

import numpy as np
import pandas as pd

np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════
# PIPE MATERIAL: Carbon Steel Schedule 40 (4" NPS, ASTM A106 Gr.B)
# ═══════════════════════════════════════════════════════════════════
T0 = 5.5       # Initial wall thickness (mm)
Tc = 3.0        # Minimum allowable thickness (mm) — ASME B31.3
                 # based on pressure design + corrosion allowance

# ═══════════════════════════════════════════════════════════════════
# SIMULATION PARAMETERS
# ═══════════════════════════════════════════════════════════════════
NUM_SEGMENTS       = 10_000
STEPS_PER_SEGMENT  = 400   # each step = 1 month (~25 years total)
TOTAL_SAMPLES      = NUM_SEGMENTS * STEPS_PER_SEGMENT  # 30,000

# Each timestep represents 1 month (0.0833 years)
DAYS_PER_MONTH = 30.4375  # Standard average month
MONTHS_PER_STEP    = 1
YEARS_PER_STEP     = MONTHS_PER_STEP / 12.0

# ═══════════════════════════════════════════════════════════════════
# REALISTIC GAS & OPERATING CONDITION PROFILES
# Based on API 571, NACE MR0175, and typical sour service data
# ═══════════════════════════════════════════════════════════════════

# Segment "severity" profiles — each segment gets a random severity
# that determines its baseline operating conditions
# Severity 0 = mild service, Severity 1 = aggressive sour service

def generate_segment_conditions(severity, num_steps):
    """
    Generate realistic time-series gas readings for a pipeline segment.
    
    Severity controls the baseline:
      - Low severity (0.0–0.3): mild sweet service, low H₂S
      - Medium severity (0.3–0.6): moderate sour/sweet mix  
      - High severity (0.6–1.0): aggressive sour service, high H₂S + CO₂
    
    Over time, conditions may gradually worsen (process drift, 
    upstream changes, scale buildup altering local chemistry).
    """
    t = np.arange(num_steps)
    
    # ── Drift factor: conditions can worsen over time ──
    # Some segments stay stable, others drift toward harsher conditions
    drift_rate = np.random.uniform(0.0, 0.003)  # per month
    drift = 1.0 + drift_rate * t  # multiplier that grows over time
    drift = np.clip(drift, 1.0, 2.0)
    
    # ── H₂S (ppm) ──
    # Sour service: 1–100 ppm range per project spec
    # Mild: 1–10 ppm, Moderate: 10–40 ppm, Severe: 40–100 ppm
    h2s_base = np.random.uniform(
        1.0 + severity * 30,
        5.0 + severity * 60
    )
    h2s = h2s_base * drift + np.random.normal(0, 1.5 + severity * 3, num_steps)
    h2s = np.clip(h2s, 0, 100)
    
    # ── CO (ppm) ──
    # Refinery CO from cracking/reforming: typically 5–200 ppm
    # Higher in FCC off-gas, coker units
    co_base = np.random.uniform(
        5.0 + severity * 40,
        20.0 + severity * 120
    )
    co = co_base * (1 + drift_rate * t * 0.3) + np.random.normal(0, 5 + severity * 10, num_steps)
    co = np.clip(co, 0, 500)
    
    # ── CO₂ (ppm) ──
    # In refinery process streams: 500–15,000 ppm typical
    # Higher CO₂ → more carbonic acid corrosion
    co2_base = np.random.uniform(
        500 + severity * 3000,
        2000 + severity * 10000
    )
    co2 = co2_base * (1 + drift_rate * t * 0.5) + np.random.normal(0, 200 + severity * 500, num_steps)
    co2 = np.clip(co2, 100, 50000)
    
    # ── CH₄ (% LEL) ──
    # LEL of methane = 5% vol → 100% LEL = 5% vol
    # Normal process: 1–15% LEL, higher if micro-leaks develop
    ch4_base = np.random.uniform(
        1.0 + severity * 5,
        5.0 + severity * 15
    )
    # CH₄ can spike as wall thins (micro-leak pathway)
    ch4 = ch4_base * (1 + drift_rate * t * 0.2) + np.random.normal(0, 0.8 + severity * 2, num_steps)
    ch4 = np.clip(ch4, 0, 100)
    
    # ── O₂ (% vol) ──
    # In process gas: typically < 1% (inerted systems)
    # Air ingress at flanges/seals: can rise to 2–5%
    # O₂ accelerates corrosion significantly
    o2_base = np.random.uniform(
        0.1 + severity * 0.5,
        0.5 + severity * 2.5
    )
    o2 = o2_base * drift + np.random.normal(0, 0.1 + severity * 0.3, num_steps)
    o2 = np.clip(o2, 0, 25)
    
    # ── Flow rate (m³/h) ──
    # Typical 4" pipe: 10–50 m³/h
    flow_base = np.random.uniform(15, 45)
    flow = flow_base + np.random.normal(0, 1.5, num_steps)
    # Flow can decrease slightly as fouling/scale builds
    flow = flow * (1 - drift_rate * t * 0.05)
    flow = np.clip(flow, 5, 60)
    
    # ── Temperature (°C) ──
    # Refinery piping: 40–120°C typical for many units
    # Higher temp → faster corrosion kinetics
    temp_base = np.random.uniform(
        40 + severity * 20,
        60 + severity * 40
    )
    temp = temp_base + np.random.normal(0, 2.0, num_steps)
    # Temperature can creep up with fouling (insulating deposits)
    temp = temp * (1 + drift_rate * t * 0.02)
    temp = np.clip(temp, 20, 150)
    
    # ── Pressure (bar) ──
    # System operating range: 2–3 bar (low-pressure sampling line)
    press_base = np.random.uniform(2.0, 3.0)
    press = press_base + np.random.normal(0, 0.08, num_steps)
    press = np.clip(press, 1.5, 3.5)
    
    return h2s, co, co2, ch4, o2, flow, temp, press


def compute_corrosion_rate(h2s, co2, o2, temp, pressure):
    """
    Compute corrosion rate (mm/year) based on gas environment.
    
    Simplified model inspired by:
      - de Waard–Milliams (CO₂ corrosion)
      - NACE SP0106 (H₂S contribution)
      - API 581 RBI corrosion rate estimation
    
    For Carbon Steel in sour/sweet service:
      - Base CO₂ corrosion: function of CO₂ partial pressure & temp
      - H₂S acceleration: sour corrosion adds to base rate  
      - O₂ factor: dissolved O₂ significantly accelerates attack
      - Temperature factor: Arrhenius-like acceleration
    
    Typical rates for CS in refinery service:
      - Mild: 0.02–0.10 mm/yr
      - Moderate: 0.10–0.25 mm/yr
      - High: 0.25–0.50 mm/yr  
      - Severe: 0.50–1.50 mm/yr
    """
    
    # CO₂ partial pressure (bar) — CO₂ ppm converted using total pressure
    pCO2 = (co2 / 1e6) * pressure  # bar
    
    # H₂S partial pressure (bar)
    pH2S = (h2s / 1e6) * pressure  # bar
    
    # ── CO₂ contribution (sweet corrosion) ──
    # de Waard–Milliams simplified: CR_co2 ~ A * pCO2^0.67 * f(T)
    # Temperature factor peaks around 70–80°C for CS
    temp_factor = np.exp(-3200 * (1/(temp + 273.15) - 1/343.15))
    cr_co2 = 0.36 * (pCO2 ** 0.62) * temp_factor
    
    # ── H₂S contribution (sour corrosion) ──
    # H₂S attack on CS: accelerates with concentration
    # Low H₂S (<50 ppm) forms protective FeS scale (reduces rate)
    # High H₂S (>50 ppm) overwhelms scale, increases rate
    if isinstance(h2s, np.ndarray):
        cr_h2s = np.where(
            h2s < 20,
            0.02 * (h2s / 20),           # mild sour
            0.02 + 0.008 * (h2s - 20)    # aggressive sour
        )
    else:
        cr_h2s = 0.02 * (h2s/20) if h2s < 20 else 0.02 + 0.008 * (h2s - 20)
    
    # ── O₂ contribution ──
    # Even small O₂ (<1%) accelerates corrosion substantially
    cr_o2 = 0.05 * (o2 ** 0.8)
    
    # ── Total corrosion rate ──
    cr_total = cr_co2 + cr_h2s + cr_o2
    
    # Add measurement/model noise (±10% uncertainty)
    noise = np.random.normal(1.0, 0.10, size=cr_total.shape)
    cr_total = cr_total * noise
    
    # Clamp to realistic range for CS
    cr_total = np.clip(cr_total, 0.01, 2.5)
    
    return cr_total


# ═══════════════════════════════════════════════════════════════════
# GENERATE DATASET
# ═══════════════════════════════════════════════════════════════════

records = []

# for seg_id in range(NUM_SEGMENTS):
#     # Random severity for this segment (0 = mild, 1 = aggressive)
#     severity = np.random.beta(2, 3)  # skewed toward milder conditions
    
#     # Generate gas & operating conditions time series
#     h2s, co, co2, ch4, o2, flow, temp, press = generate_segment_conditions(
#         severity, STEPS_PER_SEGMENT
#     )
    
#     # Compute corrosion rate for each timestep
#     cr = compute_corrosion_rate(h2s, co2, o2, temp, press)
    
#     # ── Wall thickness evolution ──
#     # T(t) = T0 - cumulative_corrosion(t)
#     # Cumulative corrosion = sum of (CR_i * delta_t) for each month
#     cumulative_corrosion = np.cumsum(cr * YEARS_PER_STEP)
#     wall_thickness = T0 - cumulative_corrosion
    
#     # ── RUL calculation ──
#     # RUL = (T(t) - Tc) / CR_current
#     # Units: mm / (mm/year) = years
#     remaining_thickness = wall_thickness - Tc
#     rul_years = np.where(
#         cr > 0,
#         remaining_thickness / cr,
#         999  # effectively infinite if no corrosion
#     )
#     rul_years = np.clip(rul_years, 0, 999)
    
#     # Build records
#     for t in range(STEPS_PER_SEGMENT):
#         records.append({
#             'segment_id':                seg_id,
#             'timestep':                  t,
#             'H2S_ppm':                   round(h2s[t], 2),
#             'CO_ppm':                    round(co[t], 2),
#             'CO2_ppm':                   round(co2[t], 2),
#             'CH4_LEL_pct':               round(ch4[t], 2),
#             'O2_vol_pct':                round(o2[t], 2),
#             'flow_rate':                 round(flow[t], 2),
#             'temperature_C':             round(temp[t], 2),
#             'pressure_bar':              round(press[t], 2),
#             'Corrosion_Rate_mm_per_day': round(cr[t] / 365.0, 6),
#             'RUL_days':                 round(rul_years[t] * 365.0, 1),
#         })

for seg_id in range(NUM_SEGMENTS):
    # 1. Generate Environment
    severity = np.random.beta(2, 3)
    h2s, co, co2, ch4, o2, flow, temp, press = generate_segment_conditions(severity, STEPS_PER_SEGMENT)
    
    # 2. Compute Annual Corrosion Rate (mm/yr)
    cr_annual = compute_corrosion_rate(h2s, co2, o2, temp, press)
    
    # 3. Calculate Wall Thickness Evolution
    # Thickness at step t = T0 - sum(cr * years_per_step) up to that point
    damage_per_step = cr_annual * YEARS_PER_STEP
    cumulative_damage = np.cumsum(damage_per_step)
    wall_thickness = T0 - cumulative_damage
    
    # 4. Find the "Ground Truth" Failure Step
    # Look for the first index where the wall is below Tc
    failure_indices = np.where(wall_thickness <= Tc)[0]
    
    if len(failure_indices) > 0:
        failure_step = failure_indices[0]
    else:
        failure_step = None # Segment never fails within 25 years

    # 5. Build Records with Look-Ahead RUL
    for t in range(STEPS_PER_SEGMENT):
        # Calculate RUL based on actual future failure
        if failure_step is not None:
            # Distance to failure in steps, then converted to days
            remaining_steps = max(0, failure_step - t)
            if failure_step < t:
                continue
            actual_rul_days = remaining_steps * DAYS_PER_MONTH
        else:
            continue
            # If it never fails, we use a 'Snapshot' projection as a fallback/cap
            # This prevents infinite values in your dataset
            snapshot_rul_days = ((wall_thickness[t] - Tc) / cr_annual[t]) * 365.25
            actual_rul_days = min(snapshot_rul_days, 10000) # Cap at ~27 years

        records.append({
            'segment_id': seg_id,
            'timestep_month': t,
            'H2S_ppm': round(h2s[t], 2),
            'CO_ppm': round(co[t], 2),
            'CO2_ppm': round(co2[t], 2),
            'CH4_LEL_pct': round(ch4[t], 2),
            'O2_vol_pct': round(o2[t], 2),
            'flow_rate': round(flow[t], 2),
            'temperature_C': round(temp[t], 2),
            'pressure_bar': round(press[t], 2),
            'Wall_Thickness_mm': round(wall_thickness[t], 3),
            'Corrosion_Rate_mm_per_year': round(cr_annual[t], 4),
            'RUL_days': round(actual_rul_days, 1)
        })

df = pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════
# BUILD DATAFRAME
# ═══════════════════════════════════════════════════════════════════
df = pd.DataFrame(records)

# ═══════════════════════════════════════════════════════════════════
# SUMMARY STATISTICS
# ═══════════════════════════════════════════════════════════════════
print("=" * 65)
print("  GasGuard AI — Synthetic Corrosion Dataset v2")
print("  Pipe: CS S40 (ASTM A106 Gr.B, 4\" NPS)")
print("  T₀ = 6.02 mm | Tc = 3.0 mm")
print("  RUL = (T(t) - Tc) / Corrosion Rate  [days]")
print("=" * 65)
print(f"\nTotal samples:     {len(df):,}")
print(f"Pipeline segments:  {df['segment_id'].nunique()}")
print(f"Timesteps/segment:  {STEPS_PER_SEGMENT} (monthly readings)")
print(f"Time horizon:       {STEPS_PER_SEGMENT/12:.1f} years")

print("\n── Feature Ranges ──")
for col in ['H2S_ppm', 'CO_ppm', 'CO2_ppm', 'CH4_LEL_pct',
            'O2_vol_pct', 'flow_rate', 'temperature_C', 'pressure_bar']:
    print(f"  {col:25s}: [{df[col].min():8.2f}, {df[col].max():8.2f}]  "
          f"mean={df[col].mean():8.2f}  std={df[col].std():7.2f}")

print("\n── Corrosion Rate (mm/year) ──")
cr_col = 'Corrosion_Rate_mm_per_year'
print(f"  Min:    {df[cr_col].min():.6f}")
print(f"  Mean:   {df[cr_col].mean():.6f}")
print(f"  Median: {df[cr_col].median():.6f}")
print(f"  Max:    {df[cr_col].max():.6f}")
print(f"  Std:    {df[cr_col].std():.6f}")

# Corrosion severity distribution (API 570 thresholds, converted to mm/day)
low = (df[cr_col] < 0.125/365).sum()
mod = ((df[cr_col] >= 0.125/365) & (df[cr_col] < 0.25/365)).sum()
high = ((df[cr_col] >= 0.25/365) & (df[cr_col] < 0.50/365)).sum()
severe = (df[cr_col] >= 0.50/365).sum()
print(f"\n  Severity Distribution (API 570-like):")
print(f"    Low    (< 0.000342 mm/day):  {low:,} ({low/len(df)*100:.1f}%)")
print(f"    Medium (0.000342–0.000685):  {mod:,} ({mod/len(df)*100:.1f}%)")
print(f"    High   (0.000685–0.00137):   {high:,} ({high/len(df)*100:.1f}%)")
print(f"    Severe (≥ 0.00137):          {severe:,} ({severe/len(df)*100:.1f}%)")

print("\n── RUL (days) ──")
rul_col = 'RUL_days'
print(f"  Min:    {df[rul_col].min():.2f}")
print(f"  Mean:   {df[rul_col].mean():.2f}")
print(f"  Median: {df[rul_col].median():.2f}")
print(f"  Max:    {df[rul_col].max():.2f}")

# Segments that reach critical thickness
critical_segments = df[df[rul_col] <= 0]['segment_id'].nunique()
print(f"\n  Segments reaching critical thickness: {critical_segments}/{NUM_SEGMENTS}")

# ═══════════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════════
output_path = "corrosion_dataset_real_rul.csv"
df.to_csv(output_path, index=False)
print(f"\nDataset saved to: {output_path}")

# Quick preview
print("\n── First 5 rows ──")
print(df.head().to_string(index=False))

print("\n── Sample segment 0 (first & last 3 rows) ──")
seg0 = df[df['segment_id'] == 0]
print(seg0.head(3).to_string(index=False))
print("...")
print(seg0.tail(3).to_string(index=False))
