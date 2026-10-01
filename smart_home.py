"""Typed state and questions for the Laya smart-home experiment (simulation only)."""
from copy import deepcopy

FIELDS = {
    "light_power": ("light", "power", {"on": "Turn the room light on", "off": "Turn the room light off"}),
    "light_mode": ("light", "mode", {"night": "Set the room light to dim night mode", "normal": "Set the room light to normal bright mode"}),
    "strip_power": ("strips", "power", {"on": "Turn the Hyperion LED strips on", "off": "Turn the Hyperion LED strips off"}),
    "strip_mood": ("strips", "mood", {"relax": "Set the Hyperion LED strips to a calm relaxing mood", "focus": "Set the Hyperion LED strips to a work or study focus mood", "party": "Set the Hyperion LED strips to a colourful party mood", "movie": "Set the Hyperion LED strips to a cinema or movie mood"}),
    "tv_power": ("tv", "power", {"on": "Turn the Android TV on", "off": "Turn the Android TV off"}),
    "tv_app": ("tv", "app", {"youtube": "Open YouTube on the Android TV", "netflix": "Open Netflix on the Android TV", "prime": "Open Amazon Prime Video on the Android TV"}),
    "ac_power": ("ac", "power", {"on": "Turn the air conditioner on", "off": "Turn the air conditioner off"}),
    "ac_mode": ("ac", "mode", {"heat": "Set the air conditioner to heating mode", "cool": "Set the air conditioner to cooling mode"}),
}

DEFAULT_STATE = {
    "light": {"power": "off", "mode": "normal"},
    "strips": {"power": "off", "mood": "relax"},
    "tv": {"power": "off", "app": "youtube"},
    "ac": {"power": "off", "mode": "cool"},
}


def questions():
    result = {}
    names = {"light": "room light", "strips": "Hyperion LED strips", "tv": "Android TV", "ac": "air conditioner"}
    for qid, (device, field, choices) in FIELDS.items():
        result[qid] = {
            "type": "choice",
            "instructions": (
                f"Which {field} change does the user request for the {names[device]}? "
                "Select keep if no change is requested."
            ),
            "criteria": {
                "keep": f"No change to the {names[device]} {field}",
                **choices,
            },
        }
    return result


def jev_questions(profile="scoped"):
    """One literal decision per property; keep the original wording for A/B trials."""
    if profile == "original":
        return questions()
    if profile != "scoped":
        raise ValueError("Unknown Jev prompt profile.")
    names = {"light": "room light", "strips": "Hyperion LED strips",
             "tv": "Android TV", "ac": "air conditioner"}
    scopes = {
        "light": "The room light is the ordinary light/bulb. It supports night and normal modes.",
        "strips": "Only the Hyperion/LED strips; these have moods, not night/normal light modes.",
        "tv": "Only the Android TV/TV; YouTube, Netflix and Amazon Prime are its apps.",
        "ac": "Only the AC/air conditioner; heat/heating and cool/cooling are its modes.",
    }
    result = {}
    for qid, (device, field, choices) in FIELDS.items():
        name = names[device]
        rules = [
            f"Decide only the {name} {field}. Instructions for other devices or properties do not apply.",
            "Use keep when this property is not requested, is to remain unchanged, or the target/value is unclear.",
            "A negated action is not a request for its opposite: 'do not turn on' alone means keep, not off.",
        ]
        if field == "power":
            rules.extend([
                "Changing a mode, mood or app alone leaves power unchanged. Only an explicit power request selects on/off.",
                "A power command for all devices/everything applies here. All lights includes the room light and LED strips, not TV or AC.",
            ])
        else:
            rules.append("A power command alone, including 'turn everything off', leaves this setting unchanged.")
        result[qid] = {
            "type": "choice",
            "instructions": {
                "question": f"Which {field} setting does the user explicitly request for the {name}?",
                "device_scope": scopes[device],
                "rules": rules,
            },
            "criteria": {
                "keep": f"The user does not request a new {name} {field}; this includes omission, leave unchanged, negation without a positive replacement, or an unclear/unsupported value.",
                **{label: f"The user explicitly requests this for the {name}: {description}."
                   for label, description in choices.items()},
            },
        }
    return result


def validate_state(state):
    if not isinstance(state, dict) or set(state) != set(DEFAULT_STATE):
        raise ValueError("State must contain light, strips, tv and ac.")
    for device, fields in DEFAULT_STATE.items():
        if not isinstance(state[device], dict) or set(state[device]) != set(fields):
            raise ValueError(f"Invalid properties for {device}.")
    for device, field, choices in FIELDS.values():
        if state[device][field] not in choices:
            raise ValueError(f"Invalid value for {device}.{field}.")


def project_answers(state, answers, threshold):
    """Validate model labels and return a proposal; never control a real device."""
    validate_state(state)
    proposed = deepcopy(state)
    decisions, changes = [], []
    for qid, (device, field, choices) in FIELDS.items():
        answer = answers[qid]
        selected = answer["choice"]
        if selected not in {"keep", *choices}:
            raise ValueError(f"Unexpected model label for {qid}: {selected}")
        confidence = float(answer["answer_confidence"])
        decision = {"id": qid, "device": device, "field": field, "choice": selected,
                    "answer_confidence": confidence, "low_confidence": confidence < threshold,
                    "provider_confidence": answer.get("confidence"),
                    "probabilities": answer.get("probabilities", {})}
        decisions.append(decision)
        if selected != "keep" and selected != state[device][field]:
            change = {**decision, "before": state[device][field], "after": selected}
            changes.append(change)
            proposed[device][field] = selected
    return {"proposed_state": proposed, "changes": changes, "decisions": decisions}
