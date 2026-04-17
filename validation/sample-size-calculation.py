"""Sample size calculation for the Retina Scan AI validation study.

Computes the sample size required to estimate sensitivity with a desired
half-width of confidence interval, given expected sensitivity and disease
prevalence.

Reference:
    Buderer NM. Statistical methodology: I. Incorporating the prevalence of
    disease into the sample size calculation for sensitivity and specificity.
    Acad Emerg Med. 1996;3(9):895-900.

Usage:
    python sample-size-calculation.py \\
        --expected-sensitivity 0.90 \\
        --ci-half-width 0.05 \\
        --prevalence 0.18 \\
        --confidence 0.95
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass


def z_score(confidence: float) -> float:
    """Two-sided z-score for the given confidence level."""
    from statistics import NormalDist

    alpha = 1 - confidence
    return NormalDist().inv_cdf(1 - alpha / 2)


def cases_for_sensitivity(
    expected_sensitivity: float,
    ci_half_width: float,
    confidence: float = 0.95,
) -> int:
    """Number of disease-positive cases needed."""
    z = z_score(confidence)
    p = expected_sensitivity
    n = (z**2) * p * (1 - p) / (ci_half_width**2)
    return int(math.ceil(n))


def total_sample_for_sensitivity(
    expected_sensitivity: float,
    ci_half_width: float,
    prevalence: float,
    confidence: float = 0.95,
) -> int:
    """Total population needed given the disease prevalence."""
    cases = cases_for_sensitivity(expected_sensitivity, ci_half_width, confidence)
    total = cases / prevalence
    return int(math.ceil(total))


@dataclass
class SampleSizeResult:
    expected_sensitivity: float
    ci_half_width: float
    prevalence: float
    confidence: float
    required_cases: int
    required_total: int


def calculate(
    expected_sensitivity: float,
    ci_half_width: float,
    prevalence: float,
    confidence: float = 0.95,
) -> SampleSizeResult:
    cases = cases_for_sensitivity(expected_sensitivity, ci_half_width, confidence)
    total = total_sample_for_sensitivity(
        expected_sensitivity, ci_half_width, prevalence, confidence
    )
    return SampleSizeResult(
        expected_sensitivity=expected_sensitivity,
        ci_half_width=ci_half_width,
        prevalence=prevalence,
        confidence=confidence,
        required_cases=cases,
        required_total=total,
    )


def adequacy_check(
    enrolled_n: int,
    prevalence: float,
    expected_sensitivity: float = 0.90,
    ci_half_width: float = 0.05,
    confidence: float = 0.95,
) -> dict:
    """Retrospective check on whether an enrolled-n is adequate."""
    required = total_sample_for_sensitivity(
        expected_sensitivity, ci_half_width, prevalence, confidence
    )
    expected_cases = int(enrolled_n * prevalence)
    required_cases = cases_for_sensitivity(expected_sensitivity, ci_half_width, confidence)
    return {
        "enrolled_n": enrolled_n,
        "expected_cases_at_prevalence": expected_cases,
        "required_total": required,
        "required_cases": required_cases,
        "adequate": enrolled_n >= required,
        "case_adequate": expected_cases >= required_cases,
        "enrollment_ratio": enrolled_n / required if required else float("inf"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample size calculator")
    parser.add_argument(
        "--expected-sensitivity",
        type=float,
        default=0.90,
        help="Expected sensitivity of the test under evaluation",
    )
    parser.add_argument(
        "--ci-half-width",
        type=float,
        default=0.05,
        help="Desired half-width of the 95% CI on sensitivity",
    )
    parser.add_argument(
        "--prevalence",
        type=float,
        required=True,
        help="Expected disease prevalence in the screened population",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Confidence level (default 0.95)",
    )
    parser.add_argument(
        "--enrolled-n",
        type=int,
        default=None,
        help="If provided, check whether this enrollment is adequate",
    )

    args = parser.parse_args(argv)

    if not (0 < args.expected_sensitivity < 1):
        print("ERROR: --expected-sensitivity must be between 0 and 1", file=sys.stderr)
        return 2
    if not (0 < args.prevalence < 1):
        print("ERROR: --prevalence must be between 0 and 1", file=sys.stderr)
        return 2
    if not (0 < args.confidence < 1):
        print("ERROR: --confidence must be between 0 and 1", file=sys.stderr)
        return 2

    result = calculate(
        args.expected_sensitivity,
        args.ci_half_width,
        args.prevalence,
        args.confidence,
    )

    print("Sample size for sensitivity estimation")
    print("-" * 60)
    print(f"Expected sensitivity:    {result.expected_sensitivity:.2f}")
    print(f"CI half-width (95%):     {result.ci_half_width:.2f}")
    print(f"Disease prevalence:      {result.prevalence:.2f}")
    print(f"Confidence level:        {result.confidence:.2f}")
    print()
    print(f"Required disease-positive cases: {result.required_cases}")
    print(f"Required total enrollment:       {result.required_total}")

    if args.enrolled_n is not None:
        print()
        print("Adequacy check")
        print("-" * 60)
        check = adequacy_check(
            args.enrolled_n,
            args.prevalence,
            args.expected_sensitivity,
            args.ci_half_width,
            args.confidence,
        )
        print(f"Enrolled n:              {check['enrolled_n']}")
        print(f"Expected cases:          {check['expected_cases_at_prevalence']}")
        print(f"Required cases:          {check['required_cases']}")
        print(f"Adequate (total):        {check['adequate']}")
        print(f"Adequate (cases):        {check['case_adequate']}")
        print(f"Enrollment ratio:        {check['enrollment_ratio']:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
