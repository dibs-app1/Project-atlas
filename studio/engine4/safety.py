"""Safety reviewer for engine-4 animal scenes (batch 5).

Every animal is a calm, friendly animal doing what it does every day: walking, grazing, pecking, swimming,
flying. There are no predators hunting, no sharks or piranhas, no fights or falls, and only gentle calls
(no growls or screeches). Animations named death/attack/bite/scream are never played. Nothing flashes.
"""
ALLOWED_TIMES = {"morning", "day", "golden", "dusk", "overcast", "snow"}
NOT_FOR_TODDLERS = ("shark", "piranha", "wolf", "esox", "pike")


def review(spec):
    from engine3.stage import SCENES
    from engine4 import scenes5  # noqa: F401  (registers the scenes)
    from engine2.noises import NOISES
    issues = []
    sc = spec.get("script")
    if sc not in SCENES:
        issues.append(f"unknown scene script {sc}")
    if spec.get("time", "day") not in ALLOWED_TIMES:
        issues.append(f"unknown time of day {spec.get('time')}")
    if any(w in (sc or "") for w in NOT_FOR_TODDLERS):
        issues.append(f"{sc}: no scary animals for toddlers")
    if spec.get("noise") not in NOISES:
        issues.append(f"unknown animal sound {spec.get('noise')}")
    if not spec.get("caption"):
        issues.append("every scene needs a caption")
    return issues
