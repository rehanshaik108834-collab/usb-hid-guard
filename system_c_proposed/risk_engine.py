"""Layer 4: combine descriptor, timing and content signals into one risk score."""
import statistics


def compute(d_points, d_reasons, times, analyzer, pc):
    w = pc["weights"]
    total = d_points
    reasons = list(d_reasons)
    if len(times) >= pc["min_keys"]:
        gaps = [1000.0 * (b - a) for a, b in zip(times, times[1:])]
        med = statistics.median(gaps)
        if med < pc["median_threshold_ms"]:
            total += w["fast_typing"]
            reasons.append(f"fast typing: median {med:.1f} ms over {len(times)} keys (+{w['fast_typing']})")
    if analyzer.launcher:
        total += w["launcher"]
        reasons.append(f"launcher shortcut {analyzer.launcher} (+{w['launcher']})")
    if analyzer.hits:
        total += w["shell_keyword"]
        reasons.append(f"shell keyword {analyzer.hits} (+{w['shell_keyword']})")
    return total, reasons
