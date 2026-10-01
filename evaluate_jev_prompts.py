"""Live, billable A/B probe via the simulator; never reads the browser's API key."""
import argparse
import json
import statistics
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from smart_home import DEFAULT_STATE, FIELDS

BASE_URL = "http://127.0.0.1:8000"
CASES = [
    ("user_example", "open youtube in android tv and set the lights to night mode",
     {"tv_app": "youtube", "light_mode": "night"}),
    ("two_devices", "Turn on the Android TV and open Netflix. Turn on the Hyperion strips and set movie mood.",
     {"tv_power": "on", "tv_app": "netflix", "strip_power": "on", "strip_mood": "movie"}),
    ("mixed_power", "Turn the light off and turn the AC on in heat mode. Leave the TV and strips unchanged.",
     {"light_power": "off", "ac_power": "on", "ac_mode": "heat"}),
    ("four_devices", "Turn the light on in night mode. Turn on the Hyperion strips in party mood. Turn the Android TV on and open Amazon Prime. Turn the AC on in cool mode.",
     {"light_power": "on", "light_mode": "night", "strip_power": "on", "strip_mood": "party",
      "tv_power": "on", "tv_app": "prime", "ac_power": "on", "ac_mode": "cool"}),
    ("negation", "Do not turn on the AC. Open Netflix on the Android TV. Leave the light and strips unchanged.",
     {"tv_app": "netflix"}),
    ("all_off", "Turn off all devices.",
     {"light_power": "off", "strip_power": "off", "tv_power": "off", "ac_power": "off"}),
]


def request(path, body=None):
    req = urllib.request.Request(BASE_URL + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="jev-1.13.0")
    parser.add_argument("--profiles", nargs="+", choices=["original", "scoped"], default=["original", "scoped"])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("jev-prompt-comparison.json"))
    args = parser.parse_args()
    if not request("/api/jev/config")["configured"]:
        raise SystemExit("Open/reload the demo to restore your saved key before running this probe.")
    print(f"Running {len(CASES) * len(args.profiles)} billable Jev API requests. No device states will be applied.", flush=True)
    output = {"started_utc": datetime.now(timezone.utc).isoformat(), "requested_model": args.model,
              "note": "Six hand-labelled cases with explicit, independent power/settings semantics. Not a representative benchmark.",
              "schemas": {}, "summary": {}, "rows": []}
    try:
        for profile in args.profiles:
            output["schemas"][profile] = request(f"/api/schema?provider=jev&prompt_profile={profile}")["questions"]
            group = []
            for name, command, overrides in CASES:
                result = request("/api/predict", {"command": command, "state": DEFAULT_STATE,
                                 "provider": "jev", "jev_model": args.model, "prompt_profile": profile})
                expected = dict.fromkeys(FIELDS, "keep") | overrides
                actual = {d["id"]: d["choice"] for d in result["decisions"]}
                errors = {k: {"expected": v, "actual": actual[k]} for k, v in expected.items() if actual[k] != v}
                row = {"profile": profile, "case": name, "command": command, "expected": expected,
                       "actual": actual, "errors": errors, "elapsed_ms": result["elapsed_ms"], "raw": result["raw"]}
                output["rows"].append(row)
                group.append(row)
                print(f"{profile}: {name}: {'FAIL' if errors else 'PASS'} {json.dumps(errors)}", flush=True)
            output["summary"][profile] = {
                "exact_requests_correct": sum(not row["errors"] for row in group), "requests": len(group),
                "switch_decisions_correct": sum(8 - len(row["errors"]) for row in group),
                "switch_decisions": 8 * len(group),
                "median_ms": statistics.median(row["elapsed_ms"] for row in group),
                "input_tokens": sum(row["raw"]["usage"].get("input_tokens", 0) for row in group),
                "output_tokens": sum(row["raw"]["usage"].get("output_tokens", 0) for row in group),
            }
    except (urllib.error.URLError, TimeoutError) as exc:
        output["failure"] = type(exc).__name__
        raise SystemExit("Probe stopped after a request error; completed results have been retained.") from None
    finally:
        args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
