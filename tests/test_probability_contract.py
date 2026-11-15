"""El porcentaje es una probabilidad solo cuando declara evento y calibración."""

import unittest

from pydantic import ValidationError

from packages.contracts.api import ProbabilityEstimate, RotationCheck


class ProbabilityContractTests(unittest.TestCase):
    def test_comparison_ranges_require_two_ordered_finite_limits(self):
        base = {
            "variable": "precipitation",
            "status": "within_range",
            "unit": "mm",
            "explanation": "Synthetic fixture",
        }
        for limits in (
            {"minimum": 1},
            {"maximum": 2},
            {"minimum": 2, "maximum": 1},
            {"minimum": 0, "maximum": float("inf")},
        ):
            with self.subTest(limits=limits), self.assertRaises(ValidationError):
                RotationCheck(**base, **limits)
        check = RotationCheck(**base, minimum=0, maximum=100)
        self.assertEqual((check.minimum, check.maximum), (0, 100))

    def test_unavailable_is_not_a_zero_probability(self):
        estimate = ProbabilityEstimate()
        self.assertEqual(estimate.status, "unavailable")
        self.assertIsNone(estimate.value)

    def test_calibrated_zero_and_fraction_keep_their_evidence(self):
        for value in (0, 0.72, 1):
            estimate = ProbabilityEstimate(
                status="calibrated",
                value=value,
                event="SYNTHETIC TEST EVENT",
                model_version="test-only",
                calibration_version="test-only",
            )
            self.assertEqual(estimate.value, value)

    def test_scores_and_untraceable_percentages_are_rejected(self):
        for body in (
            {"value": 0.8},
            {"status": "calibrated", "value": 0.8},
            {
                "status": "calibrated",
                "value": None,
                "event": "test",
                "model_version": "test",
                "calibration_version": "test",
            },
        ):
            with self.subTest(body=body), self.assertRaises(ValidationError):
                ProbabilityEstimate.model_validate(body)
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValidationError):
                ProbabilityEstimate(
                    status="calibrated",
                    value=value,
                    event="test",
                    model_version="test",
                    calibration_version="test",
                )
