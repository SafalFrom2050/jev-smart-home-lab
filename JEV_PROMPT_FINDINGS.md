# Jev multi-device prompting trial

Measured on 2026-10-01 (Asia/Tokyo), against the live Jev API using `jev-1.13.0`.

The short original prompts leave important boundary rules unstated. Each of the eight independent questions sees the whole command, so an instruction for one device can spill into another. Tightening the question and criteria improved this small trial; it does not establish general reliability.

## Changes now available in the demo

**Scoped device prompts** is the default under **Jev prompts**. **Original prompts · compare** retains the old questions for A/B testing. Local Laya continues using the original schema to preserve the earlier measurements.

- Each structured question names one device and one property, with a short description of that device's supported settings.
- `keep` explicitly includes unmentioned properties, unchanged requests, unclear or unsupported values, and negation without a positive replacement.
- A command for another device does not apply to the current property.
- Power and settings are independent. An app or mode request alone does not turn a device on; a power command alone does not change its settings.
- `Do not turn on the AC` means keep AC power, rather than turn it off.
- Whole-home power commands apply to all devices; all-lights power commands concern the room light and strips.

One API call still evaluates all eight questions. The command remains unmodified, and the application does not replace bad model answers with hand-written expected answers.

## Live comparison

Each case was run once per profile. Expected labels were written by hand; unrequested properties were labelled `keep`. We scored all eight answers, even when a mistaken answer happens to equal the current device state and produces no visible change.

| Request | Original | Scoped |
| --- | --- | --- |
| User example: open YouTube and set lights to night mode | Fail: strips mood incorrectly selected `relax` | Pass |
| TV on/Netflix plus strips on/movie | Fail: unrelated room light on/night | Pass |
| Light off plus AC on/heat; TV and strips unchanged | Pass | Pass |
| Explicit power/settings for all four devices | Pass | Pass |
| Do not turn on AC; open Netflix; other lights unchanged | Fail: TV on and AC off were inferred | Pass |
| Turn off all devices | Pass | Pass |

| Metric | Original | Scoped |
| --- | ---: | ---: |
| Entire requests correct | 3/6 | 6/6 |
| Individual switch labels correct | 43/48 | 48/48 |
| Median end-to-end response | 249.3 ms | 269.25 ms |
| Total input tokens, six requests | 6,542 | 16,124 |
| Total output tokens | 1,893 | 1,892 |

The longer prompts used about 2.46 times as many input tokens. API cost depends on account pricing. This sample is too small for a reliable latency or general accuracy claim. There are no repeated trials, broad language tests, or independent held-out cases here.

Raw evidence: `jev-prompt-baseline.json` and `jev-prompt-scoped.json`. Thirteen local application/transport checks also passed; mocked tests do not measure model intelligence.

## Your example and power behavior

`open youtube in android tv and set the lights to night mode` now returned `tv_app=youtube`, `light_mode=night`, and `keep` for all other properties in this trial.

If you want devices powered on as well, use:

> Turn on the Android TV and open YouTube. Turn on the room light and set it to night mode. Leave the Hyperion strips and AC unchanged.

YouTube is the simulator's initial app, so selecting it again produces no visible app change. A selected setting is remembered while power is off. These are application semantics, separate from model accuracy.

## Remaining limits and next experiments

Prefer one clear clause per device, with repeated device names rather than ambiguous pronouns. Semicolons or separate sentences help a reader distinguish actions, but punctuation alone is not a guarantee. Explicitly name devices that should remain unchanged when needed.

For longer requests, conditional actions, conflicts, or cross-device references, an explicit decomposition step may help more than adding more prompt rules. TypeSafe's own smart-home demo uses a generative LLM to split compound requests into atomic commands, then evaluates them individually. That would add a separate model dependency and more calls; it has not been implemented here. A sentence split or splitting blindly at `and` is insufficient: `turn on the TV and open Netflix` includes shared device references.

Current device states are not sent to the model. Commands such as `toggle it` or `make it warmer` would require a separately designed state-aware path. Continue reviewing proposed changes even when their probabilities are high.

To reproduce the six-case live A/B comparison, run the server, open the demo to restore your saved key, and explicitly invoke:

```powershell
.\.venv\Scripts\python.exe evaluate_jev_prompts.py
```

This makes **12 billable Jev requests**, never applies simulated changes, and writes `jev-prompt-comparison.json`. Pin a supported model with `--model`; compare a single profile with `--profiles scoped`. Extend `CASES` with your own failures before relying on the result.

References: [Jev 1.13 limitations and precise criteria](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [structured instructions](https://docs.typesafe.ai/primitives/advanced), [independent questions over shared state](https://docs.typesafe.ai/concepts/state), [smart-home compound request splitting](https://docs.typesafe.ai/demos/smart-home).
