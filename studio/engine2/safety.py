"""Safety reviewer for engine-2 scenes.

The scene scripts build safety in (stops at red lights and stop signs, waiting for the school bus,
barrier down at crossings, slow over speed bumps, safe following gaps, life jackets on every boat,
landings and take-offs with smooth limits). This reviewer checks each scene's settings against
those rules before anything is rendered.
"""
SPEED_CAP = {  # screen px/s; the scripts' own defaults stay below these
    "highway": 340, "car_carrier": 320, "snowplow": 160, "city_bus": 240, "speed_bumps": 250,
    "night_city": 240, "speedboat_buoys": 360, "bullet_train": 800,
}
ALLOWED_TIMES = {"dawn", "morning", "day", "golden", "dusk", "night"}
NO_NIGHT = {"car_wash", "school_bus", "construction", "seaplane", "farm_flight", "speedboat_buoys", "river_kayaks"}


def review(spec):
    from .scene import SCRIPTS
    from . import scripts_boats, scripts_cars, scripts_planes, scripts_trains  # noqa: F401
    issues = []
    sc = spec.get("script")
    if sc not in SCRIPTS:
        issues.append(f"unknown scene script {sc}")
    if spec.get("time", "day") not in ALLOWED_TIMES:
        issues.append(f"unknown time of day {spec.get('time')}")
    if spec.get("time") == "night" and sc in NO_NIGHT:
        issues.append(f"{sc} should happen in daylight")
    cap = SPEED_CAP.get(sc)
    if cap and spec.get("speed", 0) > cap:
        issues.append(f"speed {spec['speed']} is over the safe limit {cap} for {sc}")
    if spec.get("weather") == "rain" and sc in ("speedboat_buoys", "river_kayaks", "sail_race"):
        issues.append("small boats stay off the water in storms")
    if not spec.get("caption"):
        issues.append("every scene needs a caption (what children will learn)")
    return issues
