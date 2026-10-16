"""Safety reviewer for engine-3 scenes (batch 4).

Safety is built into the scenes themselves: every road vehicle keeps to its own lane (overtaking only where
the other lane is empty), trains run on rails, planes take off and land on runways, water or a snow field,
the helicopter lands on a marked helipad, boats keep to the water lanes, and nothing flashes. This reviewer
checks each scene's settings before anything is rendered.
"""
ALLOWED_TIMES = {"morning", "day", "golden", "dusk", "night"}
NO_NIGHT = {"sea_seaplane", "farm_small_plane", "farm_plane_landing", "snow_ski_plane", "snow_helicopter",
            "sea_helicopter", "city_helicopter", "sea_speedboat", "sea_sailboat", "snow_cable_car"}


def review(spec):
    from .stage import SCENES
    from . import scenes4  # noqa: F401  (registers the scenes)
    from engine2.noises import NOISES
    issues = []
    sc = spec.get("script")
    if sc not in SCENES:
        issues.append(f"unknown scene script {sc}")
    if spec.get("time", "day") not in ALLOWED_TIMES:
        issues.append(f"unknown time of day {spec.get('time')}")
    if spec.get("time") == "night" and sc in NO_NIGHT:
        issues.append(f"{sc} should happen in daylight")
    if spec.get("weather") in ("snow", "rain") and sc in ("sea_speedboat", "sea_sailboat", "sea_seaplane", "farm_small_plane"):
        issues.append("small boats and small planes stay home in bad weather")
    if spec.get("noise") not in NOISES:
        issues.append(f"unknown vehicle noise {spec.get('noise')}")
    if not spec.get("caption"):
        issues.append("every scene needs a caption")
    return issues
