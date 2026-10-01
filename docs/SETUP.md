# Detailed setup and experiment notes

Run the commands below from the repository root. The short overview is in [README.md](../README.md).

# Smart Home Lab — Jev API and local Laya

Run a local smart-home simulation using the official Jev API or locally cached Laya models. Jev is the default provider. The simulator has no actual device connection.

## Open the demo

Start it from this folder in PowerShell:

```powershell
.\Start-Laya.ps1
```

Open <http://127.0.0.1:8000>. Stop it with:

```powershell
.\Stop-Laya.ps1
```

For Jev, use the **Jev API connection** panel at the top of the page:

1. Enter your TypeSafe key in the masked **Your Jev API key** field.
2. Click **Save API key**. This saves it in this browser's local storage, activates it in the local server's memory, and clears the masked input. It does not call TypeSafe.
3. Click **Test connection** to check authentication with `GET https://api.typesafe.ai/v1/models` and load the available model names.
4. Leave **Jev model** as `jev-latest`, or enter a supported version such as `jev-1.13.0`.
5. Enter a home request and click **Ask Jev**. One `POST /v1/systemone` sends the command and eight property questions, using the selected Jev prompt profile, to TypeSafe. Calls consume your API account usage.

**Forget key** removes the key from browser local storage and the local server's memory. After a server restart, opening or reloading the page automatically restores the saved key to the server without calling TypeSafe. Browser storage is specific to the browser profile and site address (`127.0.0.1:8000`); clearing this site's browser data removes it. The key is stored without encryption, as requested. It is never included in URLs or returned API responses, and API error messages are sanitised. Use this local page to enter the key; there is no need to paste it into chat. The model selection and questions remain visible for inspection. The current home state stays in the simulator and is not sent to Jev.

Select **Laya · local CPU** under **Decision provider** to use the original offline experiment.

The simulator contains:

| Device | Power | Other switch |
| --- | --- | --- |
| Room light | On / Off | Night / Normal |
| Hyperion LED strips | On / Off | Relax / Focus / Party / Movie |
| Android TV | On / Off | YouTube / Netflix / Amazon Prime |
| AC | On / Off | Heat / Cool |

1. Enter a request or choose an example.
2. Select Jev API or local Laya. Laya additionally offers Auto route, English, or Multilingual.
3. Press **Ask Jev** / **Ask Laya**, or **Ctrl+Enter**.
4. Review every proposed change and its probability. Below-threshold proposals start unchecked. The 75% default is an experimental review setting, not a fitted reliability threshold.
5. Apply the selected changes to the simulation. You can also edit each device manually.

Try: `Turn the light on and set it to night mode.` Then compare with `Do not turn the light on. Leave everything unchanged.` Try the Japanese and Romanized Nepali examples with both checkpoints.

Power and modes/apps are independent in this experiment. `Open Netflix` changes the selected app; `Turn on the TV and open Netflix` requests both switches. Settings remain remembered while a device is off. State and history exist only in the browser session and reset on reload.

## What the model sees

The command text goes to eight independent `choice` questions in one request. Jev defaults to **Scoped device prompts**, with explicit device/property boundaries and unchanged/negation rules. Select **Original prompts · compare** for the initial short wording. The question preview follows the selected provider and profile. Local Laya retains its original prompts. Each property offers its allowed values plus `keep`. The full definitions are visible in the playground and in `smart_home.py`. The current simulated state is used by ordinary application code to calculate differences after inference; it is not included in the classifier text. In the first Laya trial, including current state caused the model to select existing settings as though they were requested.

The review threshold uses **P(answer)**: the probability assigned to the selected label. Jev does not supply Laya's `answer_confidence` field, so the adapter reads this from `probabilities[choice]`. **Provider confidence** is displayed separately in the decision table and raw output. Jev and Laya define this statistic differently; do not assume thresholds transfer between them. Jev answers are checked for valid labels, complete distributions and finite probabilities before any proposal is displayed.

The UI shows all eight answers, including answers that produce no visible change because the selected value already equals the current state. Expand **All eight decisions & probabilities** to inspect these. The application validates all selected labels. It does not rewrite incorrect model answers into correct ones or execute device APIs.

Laya language routing uses the command alone. Romanized Nepali may be routed as English; use the Multilingual override to compare. Auto routing only chooses a checkpoint; it does not itself decide device changes.

## Reproduce the local checks

```powershell
.\.venv\Scripts\python.exe -m unittest test_smart_home.py
.\.venv\Scripts\python.exe -m unittest test_jev.py
.\.venv\Scripts\python.exe evaluate_smart_home.py
```

The evaluation script explicitly selects **Laya** and requires the server running on port 8000. It takes several minutes, runs 15 hand-labelled commands on each local checkpoint, then two automatic routing probes, and saves outputs to `smart-home-results.json`. It does not use the Jev key or make hosted inference calls. Concurrent inference receives HTTP 503.

Jev transport and application checks use mocked provider responses and make no external calls. They cover the official request contract, response projection, separate certainty measures, key save/forget, secret redaction, missing-key handling, invalid responses, and authentication/rate-limit/timeout failures. A live six-case comparison on `jev-1.13.0` was run on 2026-10-01: original prompts got 3/6 requests completely correct, scoped prompts 6/6. This small trial does not establish general reliability; see `JEV_PROMPT_FINDINGS.md` for raw evidence, token usage, remaining limits, and a reproducible probe. `evaluate_jev_prompts.py` is a separate live script that makes 12 billable API calls when explicitly run.

Read `LAYA_FINDINGS.md` for measured results and model limitations. `test_smart_home.py` verifies the deterministic application boundary, not model intelligence.

## Installed environment

- Windows, Intel Core i5-1335U, about 32 GB RAM, CPU inference with four Torch threads.
- Python 3.12.14; Laya 0.3.22 from the linked source repository; PyTorch 2.14.1+cpu; Transformers 5.18.0.
- Laya source commit: `6d942c92081fbc139e736bbd9ac0023223c29b7f`.
- Model bundle revision: `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.
- English and multilingual weights cached under `.cache/huggingface`. The task-specific typed-decisions checkpoint is not downloaded and cannot be selected in this UI.
- Exact installed dependencies: `requirements-lock.txt`; cache record: `model-manifest.json`.

The server binds to `127.0.0.1`. Laya runs with `HF_HUB_OFFLINE=1`; Jev calls the fixed official `https://api.typesafe.ai/v1` endpoint over HTTPS with a Bearer key. Redirects are not followed and API requests are not automatically retried. The first request to each local checkpoint still needs to build the model in RAM. Logs are in `logs/server.stderr.log` and `logs/server.stdout.log`.

Official Jev references: [API contract](https://docs.typesafe.ai/api), [models and aliases](https://docs.typesafe.ai/models), [confidence](https://docs.typesafe.ai/confidence). Live inference requires internet access and a valid TypeSafe account/key.

To rebuild, create a Python 3.12 virtual environment and run `.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu` from the repository root. The lock installs Laya directly from the pinned public Git commit; the upstream checkout is not vendored here. Run `.\.venv\Scripts\python.exe download_models.py` with network access to populate the pinned cache. Laya inference subsequently runs offline. This installation leaves the machine's bundled Python packages unchanged.

The upstream generic playground is also available with `.\.venv\Scripts\python.exe run_demo.py --device cpu --no-preload --port 8001`. It uses `/predict`; the smart-home app uses `/api/predict`.
