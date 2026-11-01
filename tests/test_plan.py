"""Planner tests: the properties that make this safe to run unattended."""

from __future__ import annotations

import unittest

from provisioner.models import Config, ConfigError, Employee, UserState
from provisioner.plan import build_plan

CONFIG = Config(
    allowed_domains=("example.com",),
    allowed_ous=("/Engineering", "/Operations", "/Leavers"),
    leavers_ou="/Leavers",
    default_license_sku="Google-Apps-For-Business",
)


def employee(**overrides):
    data = {
        "email": "new.hire@example.com",
        "first_name": "New",
        "last_name": "Hire",
        "org_unit": "/Engineering",
        "groups": ("eng-core",),
        "license_sku": None,
        "status": "active",
    }
    data.update(overrides)
    return Employee(**data)


def kinds(actions):
    return [a.kind for a in actions]


class JoinerTests(unittest.TestCase):
    def test_new_hire_gets_created_then_groups_then_licence(self):
        plan = build_plan([employee()], {}, CONFIG)

        self.assertEqual(kinds(plan), ["create_user", "add_to_group", "assign_license"])
        self.assertEqual(plan[0].payload["orgUnitPath"], "/Engineering")
        self.assertTrue(plan[0].payload["changePasswordAtNextLogin"])
        self.assertEqual(plan[-1].payload["skuId"], "Google-Apps-For-Business")

    def test_user_already_correct_produces_no_actions(self):
        existing = {
            "new.hire@example.com": UserState(
                email="new.hire@example.com",
                org_unit="/Engineering",
                groups=frozenset({"eng-core"}),
                license_sku="Google-Apps-For-Business",
            )
        }
        self.assertEqual(build_plan([employee()], existing, CONFIG), [])

    def test_mover_only_gets_the_diff(self):
        existing = {
            "new.hire@example.com": UserState(
                email="new.hire@example.com",
                org_unit="/Operations",
                groups=frozenset({"eng-core", "ops-oncall"}),
                license_sku="Google-Apps-For-Business",
            )
        }
        plan = build_plan([employee(groups=("eng-core", "data-team"))], existing, CONFIG)

        self.assertEqual(kinds(plan), ["move_user", "add_to_group"])
        self.assertEqual(plan[0].detail, "/Operations -> /Engineering")
        self.assertEqual(plan[1].target, "data-team")

    def test_returning_hire_is_unsuspended(self):
        existing = {
            "new.hire@example.com": UserState(
                email="new.hire@example.com",
                org_unit="/Engineering",
                suspended=True,
                groups=frozenset({"eng-core"}),
                license_sku="Google-Apps-For-Business",
            )
        }
        self.assertEqual(kinds(build_plan([employee()], existing, CONFIG)), ["unsuspend_user"])

    def test_per_employee_licence_overrides_the_default(self):
        plan = build_plan([employee(license_sku="Google-Apps-Enterprise")], {}, CONFIG)
        self.assertEqual(plan[-1].payload["skuId"], "Google-Apps-Enterprise")


class LeaverTests(unittest.TestCase):
    def setUp(self):
        self.existing = {
            "leaver@example.com": UserState(
                email="leaver@example.com",
                org_unit="/Engineering",
                groups=frozenset({"eng-core", "on-call"}),
                license_sku="Google-Apps-For-Business",
            )
        }
        self.leaver = employee(email="leaver@example.com", status="leaver")

    def test_suspension_comes_before_anything_else(self):
        plan = build_plan([self.leaver], self.existing, CONFIG)
        self.assertEqual(kinds(plan)[0], "suspend_user")

    def test_leaver_is_moved_and_removed_from_every_group(self):
        plan = build_plan([self.leaver], self.existing, CONFIG)
        self.assertIn("move_user", kinds(plan))
        self.assertEqual(sum(1 for k in kinds(plan) if k == "remove_from_group"), 2)
        move = next(a for a in plan if a.kind == "move_user")
        self.assertEqual(move.payload["orgUnitPath"], "/Leavers")

    def test_licence_is_never_reclaimed_on_offboarding(self):
        # Reclaiming the seat early destroys the Drive the audit will ask for.
        for action in build_plan([self.leaver], self.existing, CONFIG):
            self.assertNotIn(action.kind, {"assign_license", "revoke_license"})

    def test_already_offboarded_leaver_produces_no_actions(self):
        done = {
            "leaver@example.com": UserState(
                email="leaver@example.com", org_unit="/Leavers", suspended=True
            )
        }
        self.assertEqual(build_plan([self.leaver], done, CONFIG), [])

    def test_unknown_leaver_is_not_invented(self):
        self.assertEqual(build_plan([self.leaver], {}, CONFIG), [])


class PolicyTests(unittest.TestCase):
    def test_typo_in_org_unit_is_refused(self):
        with self.assertRaises(ConfigError):
            build_plan([employee(org_unit="/Enginering")], {}, CONFIG)

    def test_foreign_domain_is_refused(self):
        with self.assertRaises(ConfigError):
            build_plan([employee(email="someone@gmail.com")], {}, CONFIG)

    def test_child_of_allowed_ou_is_allowed(self):
        plan = build_plan([employee(org_unit="/Engineering/Platform/Data")], {}, CONFIG)
        self.assertEqual(plan[0].payload["orgUnitPath"], "/Engineering/Platform/Data")

    def test_policy_is_checked_before_any_action_is_planned(self):
        bad = employee(email="someone@gmail.com")
        with self.assertRaises(ConfigError):
            build_plan([employee(), bad], {}, CONFIG)


if __name__ == "__main__":
    unittest.main()
