"""Retry behaviour, and the offline fake that the demo runs on."""

from __future__ import annotations

import unittest

from provisioner.directory import (
    FakeDirectory,
    FakeHttpError,
    RetryableError,
    call_with_retry,
    dump_snapshot,
    load_snapshot,
)
from provisioner.models import Action, UserState


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def test_quota_error_is_retried_with_exponential_backoff(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise FakeHttpError(429)
            return "ok"

        result = call_with_retry(flaky, sleep=self.sleep, base_delay=0.5)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(self.sleeps, [0.5, 1.0])

    def test_retry_after_header_wins_over_backoff(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise FakeHttpError(429, retry_after=2.5)
            return "ok"

        call_with_retry(flaky, sleep=self.sleep)

        self.assertEqual(self.sleeps, [2.5])

    def test_client_error_is_not_retried(self):
        calls = {"n": 0}

        def broken():
            calls["n"] += 1
            raise FakeHttpError(400)

        with self.assertRaises(FakeHttpError):
            call_with_retry(broken, sleep=self.sleep)

        self.assertEqual(calls["n"], 1)
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_max_attempts(self):
        def always_limited():
            raise FakeHttpError(503)

        with self.assertRaises(RetryableError):
            call_with_retry(always_limited, max_attempts=3, sleep=self.sleep)

        self.assertEqual(len(self.sleeps), 2)

    def test_first_call_success_does_not_sleep(self):
        self.assertEqual(call_with_retry(lambda: 1, sleep=self.sleep), 1)
        self.assertEqual(self.sleeps, [])


class FakeDirectoryTests(unittest.TestCase):
    def test_create_then_group_then_licence(self):
        directory = FakeDirectory()
        for action in [
            Action("create_user", "a@example.com", "", {"primaryEmail": "a@example.com", "orgUnitPath": "/Engineering"}),
            Action("add_to_group", "eng-core", "", {"email": "a@example.com"}),
            Action("assign_license", "a@example.com", "", {"skuId": "Google-Apps-For-Business"}),
        ]:
            directory.execute(action)

        user = directory.snapshot()["a@example.com"]
        self.assertEqual(user.org_unit, "/Engineering")
        self.assertEqual(user.groups, frozenset({"eng-core"}))
        self.assertEqual(user.license_sku, "Google-Apps-For-Business")

    def test_retry_calls_inject_quota_errors(self):
        directory = FakeDirectory(retry_calls=2)
        action = Action("create_user", "b@example.com", "", {"primaryEmail": "b@example.com", "orgUnitPath": "/X"})

        with self.assertRaises(FakeHttpError):
            directory.execute(action)
        call_with_retry(lambda: directory.execute(action), sleep=lambda _: None)

        self.assertIn("b@example.com", directory.snapshot())

    def test_snapshot_round_trip(self):
        import tempfile
        from pathlib import Path

        users = {
            "a@example.com": UserState("a@example.com", "/Engineering", groups=frozenset({"eng-core"})),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            dump_snapshot(users, path)
            self.assertEqual(load_snapshot(path), users)


if __name__ == "__main__":
    unittest.main()
