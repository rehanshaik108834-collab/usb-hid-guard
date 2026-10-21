"""Layer 4: combine descriptor, timing and content signals into one risk score."""


def compute(d_points, d_reasons, d_fired, usblock_reason, analyzer, pc):
    """Returns (total, reasons, fired). fired = names of the weights that applied.
    usblock_reason: what USBlock's unchanged rule found so far (common/usblock.RES), or None."""
    w = pc["weights"]
    total = d_points
    reasons = list(d_reasons)
    fired = set(d_fired)
    if usblock_reason:  # timing layer: USBlock's rule (or its YubiKey MODHEX check) fired
        total += w["fast_typing"]
        fired.add("fast_typing")
        reasons.append(f"USBlock: {usblock_reason.split(' after ')[0]} (+{w['fast_typing']})")
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
    """True if a sign that no person can produce applied (USBlock's rule by default).
    Without one, a high score is strong suspicion but not proof, so the device is held for a
    code check instead of being blocked for good."""
    return bool(set(fired) & set(pc.get("proof_signals", ["fast_typing"])))
