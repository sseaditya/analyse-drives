# gpx_function.py

import gpxpy
import json
from math import radians, cos, sin, asin, sqrt
from collections import defaultdict

# --- Constants & Helper Functions (tuned for backend use) ---
G = 9.80665
CAR_MASS = 1350.0
DRAG_COEFFICIENT = 0.31
FRONTAL_AREA = 2.04
ROLLING_RESISTANCE = 0.015
AC_POWER_DRAW_WATTS = 1500.0
ENGINE_EFFICIENCY = 0.28
AIR_DENSITY = 1.225
FUEL_ENERGY_DENSITY = 34.2 * 1e6
IDLE_FUEL_RATE_LPH_AC_ON = 1.4

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def exponential_moving_average(data, alpha=0.5):
    if not data: return []
    smoothed = [data[0]]
    for i in range(1, len(data)):
        new_val = alpha * data[i] + (1 - alpha) * smoothed[-1]
        smoothed.append(new_val)
    return smoothed

# --- Main Analysis Function (Refactored for Backend) ---
def analyze_gpx_data(gpx_file_content):
    """
    Analyzes GPX file content and returns a dictionary of calculated statistics.
    This version is stripped of all printing and plotting for backend use.
    """
    gpx = gpxpy.parse(gpx_file_content)

    # --- Configurable Parameters ---
    resolution = 2.0
    alpha = 0.7
    brake_threshold_g = -0.3
    bin_size = 10

    segments_data = []
    absolute_dist = 0.0
    analysis_dist, analysis_time = 0.0, 0.0
    analysis_fuel_L = 0.0
    last_speed_ms = None

    for track in gpx.tracks:
        for segment in track.segments:
            points = segment.points
            i = 0
            while i < len(points) - 1:
                j = i + 1
                while j < len(points):
                    p1, p2 = points[i], points[j]
                    t1, t2 = p1.time, p2.time
                    if not (t1 and t2):
                        j += 1
                        continue

                    dt = (t2 - t1).total_seconds()
                    if dt >= resolution:
                        d = haversine(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
                        absolute_dist += d
                        v = (d / dt) * 3.6 if dt > 0 else 0
                        current_speed_ms = v / 3.6

                        # Fuel Calculation
                        p1_elev = p1.elevation if p1.elevation is not None else 0
                        p2_elev = p2.elevation if p2.elevation is not None else 0
                        delta_elevation = p2_elev - p1_elev
                        segment_fuel_L = 0.0
                        if current_speed_ms < 1.0:
                            segment_fuel_L = (IDLE_FUEL_RATE_LPH_AC_ON / 3600) * dt
                        elif last_speed_ms is not None:
                            accel = (current_speed_ms - last_speed_ms) / dt
                            force_drag = 0.5 * AIR_DENSITY * FRONTAL_AREA * DRAG_COEFFICIENT * (current_speed_ms**2)
                            force_rolling = ROLLING_RESISTANCE * CAR_MASS * G
                            force_gravity = CAR_MASS * G * (delta_elevation / d) if d > 0 else 0
                            force_accel = CAR_MASS * accel
                            power_for_motion = max(0, (force_drag + force_rolling + force_gravity + force_accel) * current_speed_ms)
                            total_power_output = power_for_motion + AC_POWER_DRAW_WATTS
                            energy_from_fuel = (total_power_output * dt) / ENGINE_EFFICIENCY
                            segment_fuel_L = energy_from_fuel / FUEL_ENERGY_DENSITY
                        
                        analysis_fuel_L += segment_fuel_L
                        last_speed_ms = current_speed_ms
                        
                        analysis_dist += d
                        analysis_time += dt
                        segments_data.append({'v': v, 'time': t2, 'd': d, 'dt': dt})
                        break
                    j += 1
                i = j

    if not segments_data:
        raise ValueError("No usable data found in the GPX file.")

    raw_speeds = [s['v'] for s in segments_data]
    raw_times = [s['time'] for s in segments_data]
    speeds = exponential_moving_average(raw_speeds, alpha=alpha)

    # --- Calculate Final Stats ---
    total_distance_km = analysis_dist / 1000.0
    total_time_seconds = analysis_time
    avg_speed_kph = (total_distance_km / (total_time_seconds / 3600)) if total_time_seconds > 0 else 0
    top_speed_kph = max(speeds) if speeds else 0
    fuel_efficiency_kml = total_distance_km / analysis_fuel_L if analysis_fuel_L > 0 else 0

    # Braking Events
    braking_events = []
    brake_threshold_ms2 = brake_threshold_g * G
    for i in range(1, len(speeds)):
        dt = (raw_times[i] - raw_times[i-1]).total_seconds()
        if dt > 0:
            a_ms2 = ((speeds[i] - speeds[i-1]) / 3.6) / dt
            if a_ms2 < brake_threshold_ms2:
                braking_events.append({'decel_g': round(a_ms2 / G, 2), 'speed_from': round(speeds[i-1]), 'speed_to': round(speeds[i])})

    # Speed Distribution
    bin_dist = defaultdict(float)
    for i in range(len(speeds)):
        speed_bin = int(speeds[i] // bin_size) * bin_size
        bin_dist[speed_bin] += segments_data[i]['d']
    
    speed_distribution = {f"{b}-{b+bin_size}": round(d/1000, 2) for b, d in sorted(bin_dist.items())}

    # --- Return results dictionary matching DB schema ---
    return {
        "total_distance_km": round(total_distance_km, 2),
        "avg_speed_kph": round(avg_speed_kph, 2),
        "top_speed_kph": round(top_speed_kph, 2),
        "total_time_seconds": int(total_time_seconds),
        "fuel_efficiency_kml": round(fuel_efficiency_kml, 2),
        "braking_events": json.dumps(braking_events),
        "speed_distribution": {
            f"{b}-{b+bin_size}": {
                "distance_km": round(bin_dist[b] / 1000, 2),
                "time_seconds": int(bin_time[b])}
            for b in sorted(bin_dist.keys())
        }
    }
