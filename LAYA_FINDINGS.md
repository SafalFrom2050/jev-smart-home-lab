# Laya local evaluation — 2026-10-01, Asia/Tokyo

Laya runs locally on this machine with no inference API key. The smart-home playground is functional, but the shipped base checkpoints are not reliable controllers for the tested eight-switch schema. Keep this as a supervised experiment. The application displays real answers rather than correcting them with a hidden command parser.

## Measured on this PC

Windows; Intel Core i5-1335U; approximately 32 GB RAM; CPU inference; four Torch threads. Python 3.12.14, Laya 0.3.22, PyTorch 2.14.1+cpu, Transformers 5.18.0. Source and model revisions are recorded in docs/SETUP.md and model-manifest.json.

| Test | English | Multilingual |
| --- | ---: | ---: |
| Entire requests correct, including leaving unrelated switches alone | 0 / 15 | 1 / 15 |
| Individual switch decisions correct | 48 / 120 (40.0%) | 53 / 120 (44.2%) |
| Incorrect switch answers with P(answer) ≥ 75% | 6 | 30 |
| Warm median, eight choices per request | 7.10 s | 2.31 s |
| Warm observed range | 6.23–8.92 s | 1.95–2.87 s |

These are 15 hand-written cases, not a random sample, held-out domain benchmark, or general capability rating. Each request has eight answers, many expected to be `keep`. An answer selecting a value already in effect still counts as wrong if the request never asked for it, even though it produces no visible change in the simulator. Full evidence and probabilities are saved in `smart-home-results.json`; the test can be rerun with `evaluate_smart_home.py`.

The set covers each appliance, all-off, mixed requests, independent mode/app changes, negation, greetings, an unsupported door request, an ambiguous pronoun, Japanese, and Romanized Nepali. Some directly requested settings were recognised, but unrelated-property errors prevented whole-request success. For example, multilingual selected strip power `on` at 99.96% when asked only to turn the room light on in night mode. An ambiguous `Turn it on` switched several devices on at greater than 99% instead of abstaining. A `keep` option alone therefore does not establish an abstention policy.

The initial longer-prompt version included the current home state in JSON. It selected existing settings despite an explicit request to change the light. Removing that state and shortening the questions improved the directly requested light answers and reduced computation, but did not resolve unrelated-device changes. The measured table uses the final, simpler schema.

## Capabilities and constraints

| Area | Finding | Consequence for this project |
| --- | --- | --- |
| Output | The model emits `choice`, ordinal `score`, or `noul` P(yes) over supplied options. It does not generate explanations or plans. | Define every allowed device operation in application code. Typed output can still select the wrong operation. |
| Inputs and state | Text and JSON are encoded as text. The model has no built-in appliance connection or persistent conversational state. | This simulator maintains state separately. Speech recognition, images, device discovery, actual status feedback, and scheduling need other components. |
| Zero-shot generalisation | The author's typed-decisions benchmark reports base accuracy around 35–36%; the higher 76.6% claim is for a task-specific fine-tuned checkpoint. | The smart-home domain is not one of those four workflows. That checkpoint's headline score is not evidence of smart-home accuracy. |
| Negation | Cancellation probes document confident action selections for negated requests. Our smart-home negation cases also produced wrong changes. | Test positive and negative pairs with the exact schema and checkpoint. More instructions alone do not provide a dependable prohibition. |
| Confidence | `confidence` measures normalised entropy; `answer_confidence` is the selected answer probability. Both shipped bases need domain calibration. | The UI uses `answer_confidence`. Its 75% setting is only an inspection aid; 30 multilingual mistakes passed it in this probe. Jev thresholds cannot be transferred blindly. |
| Labels | Boolean-like option wording can dominate the state. The documented English `noul` failure needs explicit criteria/label workarounds. | Label wording, order, descriptions, and the number of options are experimental variables. Validate each version instead of assuming schema equivalence. |
| Score | Ordinal scoring is relatively weak and multilingual scoring has a documented first-position bias. | We use categorical switches only. Do not interpret a score as an accurate physical quantity. |
| Action metadata | `action.act_probability` is nearly always 1.0 in documented probes, and our raw outputs show 1.0. | It is not a permission or reliability gate. The simulator ignores it. |
| Language | English is unsuitable as a universal multilingual checkpoint; routing uses script and language heuristics. | Japanese needs the multilingual path. Latin-script Nepali can route to English; compare the explicit override. Multilingual support does not guarantee transliteration accuracy. |
| Context | English defaults to 512 tokens; multilingual defaults to 1,024. The multilingual encoder supports up to 8,192 when explicitly requested. Options and question text share the context with the request. | Long histories and large schemas can truncate or distort decisions. Check `usage.truncated`, dropped state tokens, and option diagnostics. |
| Option count | The option prompt budget is 192 tokens for English and 256 for multilingual by default. Many descriptions compete for that budget. | Keep each decision small. For large label sets, shortlist or route in stages and measure accuracy. The library and HTTP service have different size guards. |
| Speed and hardware | The advertised ~33 ms is a T4 GPU measurement for a different workload. Downloads and cold model builds are separate costs. | Our CPU eight-switch medians are seconds. Both checkpoints are cached, but each still loads into RAM on first use after server startup. No Intel GPU acceleration was validated. |
| Evidence and maturity | The package declares Beta status. Some benchmark columns have been refreshed after reproduction failures, and the fine-tuned typed-decisions figure lacks a committed raw result file according to the README. | Treat claims as author-reported evidence with stated boundaries. We verified installation, real offline inference, our small probe, and the simulator boundary. |
| Jev comparison | The repository's Jev results are published third-party numbers, not an equal-prompt run conducted by the Laya author. | The tables do not establish that Laya replaces or consistently outperforms Jev. API-format compatibility also does not imply identical model behaviour. |
| Licence and deployment | Repository and model cards identify Apache-2.0. Local inference needs no paid provider and can operate after downloading the weights. | Retain licence notices for redistribution. Real Hyperion, TV, AC and light adapters remain separate future integration work. |

The relevant distinction is between a valid bounded answer and a correct decision. Laya guarantees a structured choice mechanism; it does not guarantee that the selected action follows the request. For this home, a useful next experiment is a smaller device-routing task, carefully labelled domain examples, and fine-tuning plus calibration on separate data. Measure unintended changes and coverage, not just correct requested changes. The current demo intentionally leaves all proposals reviewable.

## Validation performed

- Real English and multilingual inference with the Hub in offline mode; cached revision pinned.
- Four deterministic unit tests: input immutability, independent power/mode projection, low-confidence visibility, and rejection of invalid state/labels.
- Local API rejects an invalid device state with HTTP 422.
- Required upstream lint and compile gates passed. Local scripts passed the same error-focused lint checks.
- Browser checks passed for real inference, selecting individual proposals, applying only reviewed light changes, manual strip/TV/AC settings, invalidation after edits, and reset. Desktop and 375-pixel mobile layouts were inspected; the mobile document had no horizontal overflow. No physical smart-home integration or hardware execution was attempted.

## Primary sources

- [Source repository and honest limits](https://github.com/NandhaKishorM/laya#honest-limits)
- [Benchmark methodology and refreshed figures](https://github.com/NandhaKishorM/laya/blob/main/BENCHMARKS.md)
- [Checkpoint files and licence](https://huggingface.co/convaiinnovations/laya)
- [Multilingual checkpoint](https://huggingface.co/convaiinnovations/laya-multilingual)
- [Negated cancellation probe, issue 377](https://github.com/NandhaKishorM/laya/issues/377)
- [Boolean label sensitivity, issue 156](https://github.com/NandhaKishorM/laya/issues/156)
- [Multilingual score position bias, issue 131](https://github.com/NandhaKishorM/laya/issues/131)
- [Uninformative action probability, issue 185](https://github.com/NandhaKishorM/laya/issues/185)

Local source inspection additionally checked `laya/agent.py`, `router.py`, `lang.py`, `common.py`, `confidence.py`, `serve.py`, and package metadata at the pinned commit. Upstream source is unchanged.
