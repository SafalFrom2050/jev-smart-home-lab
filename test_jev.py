"""Offline contract tests for Jev transport, key handling and response projection."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import jev_provider as jev
from smart_home import DEFAULT_STATE, FIELDS
from smart_home_server import app


def fixture():
    answers = {}
    for qid, (_, _, choices) in FIELDS.items():
        selected = {"light_power": "on", "light_mode": "night"}.get(qid, "keep")
        answers[qid] = {"type": "choice", "choice": selected, "confidence": 0.9,
                        "probabilities": {key: 1.0 if key == selected else 0.0 for key in {"keep", *choices}}}
    return {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 200, "output_tokens": 20}}


class JevTests(unittest.TestCase):
    def setUp(self):
        jev.forget_key()
        self.client = TestClient(app, base_url="http://127.0.0.1:8000")

    def tearDown(self):
        jev.forget_key()
        self.client.close()

    def save(self):
        return self.client.post('/api/jev/key', json={"api_key": "test-only-fake-key"})

    def test_key_lifecycle_never_returns_secret(self):
        self.assertEqual(self.save().status_code, 200)
        for url in ('/api/jev/config', '/health', '/api/schema'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('test-only-fake-key', response.text)
        self.assertTrue(self.client.get('/api/jev/config').json()['configured'])
        self.client.delete('/api/jev/key')
        self.assertFalse(jev.configured())

    def test_invalid_secret_is_not_reflected_and_cross_origin_is_rejected(self):
        response = self.client.post('/api/jev/key', json={"api_key": "secret\nwith-newline"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('secret', response.text)
        response = self.client.post('/api/jev/key', json={"api_key": "test-only-fake-key"}, headers={"Origin": "https://unrelated.example"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(jev.configured())

    def test_missing_key_makes_no_external_call(self):
        with patch('jev_provider.httpx.Client') as client:
            response = self.client.post('/api/predict', json={"command": "light on", "state": DEFAULT_STATE})
            self.assertEqual(response.status_code, 409)
            client.assert_not_called()

    def test_official_request_and_real_projection_using_mock_transport(self):
        self.save()
        with patch('jev_provider.httpx.Client') as client:
            remote = client.return_value.__enter__.return_value
            remote.request.return_value = httpx.Response(200, json=fixture())
            response = self.client.post('/api/predict', json={"command": "Turn the light on and set night mode", "state": deepcopy(DEFAULT_STATE), "provider": "jev"})
            self.assertEqual(response.status_code, 200, response.text)
            args, kwargs = remote.request.call_args
            self.assertEqual(args, ('POST', 'https://api.typesafe.ai/v1/systemone'))
            self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-only-fake-key')
            self.assertEqual(kwargs['json']['model'], 'jev-latest')
            self.assertEqual(len(kwargs['json']['questions']), 8)
            self.assertIsInstance(kwargs['json']['questions']['light_power']['instructions'], dict)
            result = response.json()
            self.assertEqual(result['prompt_profile'], 'scoped')
            self.assertEqual(result['proposed_state']['light'], {"power": "on", "mode": "night"})
            self.assertEqual(len(result['changes']), 2)
            self.assertEqual(result['proposed_state']['ac'], DEFAULT_STATE['ac'])
            self.assertNotIn('test-only-fake-key', response.text)

    def test_original_profile_is_sent_and_schema_matches_selected_provider(self):
        self.save()
        with patch('jev_provider.httpx.Client') as client:
            remote = client.return_value.__enter__.return_value
            remote.request.return_value = httpx.Response(200, json=fixture())
            response = self.client.post('/api/predict', json={
                "command": "Open Netflix", "state": DEFAULT_STATE, "prompt_profile": "original"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['prompt_profile'], 'original')
            self.assertEqual(remote.request.call_args.kwargs['json']['questions'],
                             self.client.get('/api/schema?provider=jev&prompt_profile=original').json()['questions'])
        local = self.client.get('/api/schema?provider=laya').json()
        self.assertEqual(local['prompt_profile'], 'original')
        self.assertIsInstance(local['questions']['light_power']['instructions'], str)
        self.assertEqual(self.client.get('/api/schema?prompt_profile=unknown').status_code, 422)

    def test_probability_and_provider_confidence_stay_distinct(self):
        result = fixture()
        result['answers']['light_power']['confidence'] = 0.7
        normalised = jev.normalise_response(result)
        answer = normalised['answers']['light_power']
        self.assertEqual(answer['answer_confidence'], 1.0)
        self.assertEqual(answer['confidence'], 0.7)

    def test_auth_rate_limit_timeout_errors_are_redacted(self):
        self.save()
        for status in (401, 429, 529):
            with patch('jev_provider.httpx.Client') as client:
                remote = client.return_value.__enter__.return_value
                remote.request.return_value = httpx.Response(status, text='test-only-fake-key')
                response = self.client.post('/api/jev/test')
                self.assertNotIn('test-only-fake-key', response.text)
                self.assertEqual(response.status_code, 503 if status == 529 else status)
        with patch('jev_provider.httpx.Client') as client:
            client.return_value.__enter__.return_value.request.side_effect = httpx.ReadTimeout('test-only-fake-key')
            response = self.client.post('/api/jev/test')
            self.assertEqual(response.status_code, 504)
            self.assertNotIn('test-only-fake-key', response.text)

    def test_models_endpoint_is_get_and_does_not_evaluate(self):
        self.save()
        with patch('jev_provider.httpx.Client') as client:
            remote = client.return_value.__enter__.return_value
            remote.request.return_value = httpx.Response(200, json={"models": [{"name": "jev-latest"}]})
            response = self.client.post('/api/jev/test')
            self.assertEqual(response.json(), {"connected": True, "models": ["jev-latest"]})
            self.assertEqual(remote.request.call_args.args, ('GET', 'https://api.typesafe.ai/v1/models'))

    def test_incomplete_or_invalid_provider_answers_cannot_apply(self):
        result = fixture()
        del result['answers']['ac_power']
        with self.assertRaises(jev.JevError):
            jev.normalise_response(result)
        result = fixture()
        result['answers']['tv_app']['choice'] = 'delete-files'
        with self.assertRaises(jev.JevError):
            jev.normalise_response(result)
        result['answers']['tv_app']['choice'] = []
        with self.assertRaises(jev.JevError):
            jev.normalise_response(result)
        result = fixture()
        result['answers']['tv_app']['probabilities']['youtube'] = float('nan')
        with self.assertRaises(jev.JevError):
            jev.normalise_response(result)
        self.assertNotIn('api_key', json.dumps(jev.normalise_response(fixture())))


if __name__ == '__main__':
    unittest.main()
