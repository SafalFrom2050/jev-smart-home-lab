"""Small hand-labelled model probe, not a production accuracy benchmark."""
import json
import statistics
import time
import urllib.request
from copy import deepcopy
from pathlib import Path

from smart_home import DEFAULT_STATE, FIELDS

CASES = [
    ("light_night", "Turn the light on and set it to night mode.", {"light_power": "on", "light_mode": "night"}),
    ("strips_party", "Turn on the Hyperion LED strips and set their mood to party.", {"strip_power": "on", "strip_mood": "party"}),
    ("tv_netflix", "Turn on the Android TV and open Netflix.", {"tv_power": "on", "tv_app": "netflix"}),
    ("ac_cool", "Turn the AC on and set it to cool mode.", {"ac_power": "on", "ac_mode": "cool"}),
    ("all_off", "Turn off the light, the Hyperion LED strips, the Android TV and the AC.", {"light_power": "off", "strip_power": "off", "tv_power": "off", "ac_power": "off"}),
    ("mixed", "Turn the light off. Turn the TV on and open YouTube. Leave the AC and strips unchanged.", {"light_power": "off", "tv_power": "on", "tv_app": "youtube"}),
    ("mode_only", "Set the light to normal mode. Leave its power switch unchanged.", {"light_mode": "normal"}),
    ("prime", "Open Amazon Prime Video on the TV. Do not change any power switches.", {"tv_app": "prime"}),
    ("negated_ac", "Do not turn on the AC. Leave all devices unchanged.", {}),
    ("negated_light", "Do not turn the light on. Leave everything as it is.", {}),
    ("greeting", "Hello! How are you today?", {}),
    ("unsupported", "Unlock the front door.", {}),
    ("ambiguous", "Turn it on.", {}),
    ("japanese", "エアコンをつけて、暖房モードにしてください。", {"ac_power": "on", "ac_mode": "heat"}),
    ("romanized_nepali", "batti on gara ani night mode ma rakha", {"light_power": "on", "light_mode": "night"}),
]


def request(command, model):
    body = json.dumps({"command": command, "state": deepcopy(DEFAULT_STATE),
                       "provider": "laya", "model": model, "threshold": 0.75}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/predict", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.load(response)


def main():
    rows, warmups = [], {}
    for model in ("english", "multilingual"):
        start = time.perf_counter()
        request("Turn the light on.", model)
        warmups[model] = round((time.perf_counter() - start) * 1000, 1)
        for case_id, command, overrides in CASES:
            expected = dict.fromkeys(FIELDS, "keep") | overrides
            result = request(command, model)
            actual = {d["id"]: d["choice"] for d in result["decisions"]}
            errors = {key: {"expected": expected[key], "actual": actual[key],
                            "answer_confidence": next(d["answer_confidence"] for d in result["decisions"] if d["id"] == key)}
                      for key in expected if actual[key] != expected[key]}
            rows.append({"case": case_id, "model": model, "command": command,
                         "expected": expected, "actual": actual, "errors": errors,
                         "elapsed_ms": result["elapsed_ms"], "raw": result["raw"]})
            print(f"{model:12} {case_id:18} {'PASS' if not errors else 'FAIL'} {result['elapsed_ms']} ms "
                  f"{json.dumps(errors)}", flush=True)
    for case_id, command, overrides in CASES[-2:]:
        result = request(command, "auto")
        rows.append({"case": case_id, "model": "auto", "routing": result["routing"],
                     "elapsed_ms": result["elapsed_ms"], "actual": {d["id"]: d["choice"] for d in result["decisions"]},
                     "raw": result["raw"]})
    summary = {}
    for model in ("english", "multilingual"):
        group = [r for r in rows if r["model"] == model]
        durations = sorted(r["elapsed_ms"] for r in group)
        summary[model] = {"exact_requests_correct": sum(not r["errors"] for r in group),
                          "requests": len(group), "switch_decisions_correct": sum(8-len(r["errors"]) for r in group),
                          "switch_decisions": len(group)*8, "warm_median_ms": statistics.median(durations),
                          "warm_min_ms": min(durations), "warm_max_ms": max(durations),
                          "wrong_at_or_above_75_percent": sum(e["answer_confidence"] >= 0.75 for r in group for e in r["errors"].values())}
    output = {"note": "15 hand-written cases per checkpoint; includes many keep labels. Not representative production accuracy. Eight independent choices per request, CPU, 4 threads.",
              "warmup_ms": warmups, "summary": summary, "rows": rows}
    destination = Path(__file__).resolve().parent / "smart-home-results.json"
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
