def calculate_multiplier(duration: float) -> float:
    """
    Calculate hardware multiplier based on benchmark duration.
    Baseline: RTX 3060 takes ~35s -> 1.0x
    """
    if duration <= 0:
        return 0.0

    baseline = 35.0
    multiplier = baseline / duration

    # Cap at 20x to prevent exploits
    return round(min(multiplier, 20.0), 2)
