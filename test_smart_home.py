"""Check the application boundary independently of probabilistic model accuracy."""
import unittest
from copy import deepcopy
from smart_home import DEFAULT_STATE, FIELDS, project_answers, validate_state


class ProjectionTests(unittest.TestCase):
    def answers(self):
        return {key: {"choice": "keep", "answer_confidence": 0.95} for key in FIELDS}

    def test_no_change_does_not_mutate_input(self):
        state = deepcopy(DEFAULT_STATE)
        result = project_answers(state, self.answers(), 0.75)
        self.assertEqual(result["changes"], [])
        self.assertEqual(state, DEFAULT_STATE)
        self.assertIsNot(result["proposed_state"], state)

    def test_power_and_mode_are_independent_and_low_confidence_is_visible(self):
        answers = self.answers()
        answers["light_mode"] = {"choice": "night", "answer_confidence": 0.6}
        result = project_answers(deepcopy(DEFAULT_STATE), answers, 0.75)
        self.assertEqual(result["proposed_state"]["light"], {"power": "off", "mode": "night"})
        self.assertTrue(result["changes"][0]["low_confidence"])
        self.assertEqual(DEFAULT_STATE["light"]["mode"], "normal")

    def test_unknown_model_label_is_rejected(self):
        answers = self.answers()
        answers["tv_app"]["choice"] = "shell_command"
        with self.assertRaises(ValueError):
            project_answers(deepcopy(DEFAULT_STATE), answers, 0.75)

    def test_unknown_device_or_invalid_state_is_rejected(self):
        state = deepcopy(DEFAULT_STATE)
        state["door"] = {"power": "on"}
        with self.assertRaises(ValueError):
            validate_state(state)
        state = deepcopy(DEFAULT_STATE)
        state["ac"]["mode"] = "invalid"
        with self.assertRaises(ValueError):
            validate_state(state)


if __name__ == "__main__":
    unittest.main()
