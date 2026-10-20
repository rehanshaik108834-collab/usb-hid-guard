"""Layer 4: combine descriptor, timing and content signals into one risk score."""
import statistics


def compute(d_points, d_reasons, d_fired, times, analyzer, pc):
    """Returns (total, reasons, fired). fired = names of the weights that applied."""
    w = pc["weights"]
    total = d_points
    reasons = list(d_reasons)
    fired = set(d_fired)
    if len(times) >= pc["min_keys"]:
        gaps = [1000.0 * (b - a) for a, b in zip(times, times[1:])]
        med = statistics.median(gaps)
        if med < pc["median_threshold_ms"]:
            total += w["fast_typing"]
            fired.add("fast_typing")
            reasons.append(f"fast typing: median {med:.1f} ms over {len(times)} keys (+{w['fast_typing']})")
    if analyzer.launcher:
        total += w["launcher"]
        fired.add("launcher")
        reasons.append(f"launcher shortcut {analyzer.launcher} (+{w['launcher']})")
    if analyzer.hits:
        total += w["shell_keyword"]
        fired.add("shell_keyword")
        reasons.append(f"shell keyword {analyzer.hits} (+{w['shell_keyword']})")
    return total, reasons, fired


def has_proof(fired, pc):
    """True if a sign that no person can produce applied (machine-speed typing by default).
    Without one, a high score is strong suspicion but not proof, so the device is held for a
    code check instead of being blocked for good."""
    return bool(set(fired) & set(pc.get("proof_signals", ["fast_typing"])))
