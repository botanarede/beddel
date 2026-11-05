"""Pure Story 4.3 Findings and Review assessment tests."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from beddel_profile_dev.findings import (
    ASSESSMENT_BEGIN,
    ASSESSMENT_END,
    REVIEW_ASSESSMENT_SCHEMA,
    derive_findings,
    parse_review_assessment,
)

REQUIREMENTS = [
    {
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
    },
    {
        "class": "review-arch",
        "affected_point": "api",
        "criterion": "arch-ok",
        "kind": "review",
    },
]


def _review_output(
    assessments: list[dict[str, Any]], unassociated: list[dict[str, Any]] | None = None
) -> bytes:
    payload = {
        "schema": REVIEW_ASSESSMENT_SCHEMA,
        "assessments": assessments,
        "unassociated": unassociated or [],
    }
    return (
        f"{ASSESSMENT_BEGIN}\n".encode()
        + json.dumps(payload, separators=(",", ":")).encode()
        + f"\n{ASSESSMENT_END}\n".encode()
    )


def _gate(commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **REQUIREMENTS[0],
        "record": {
            "result": {
                "commands": commands,
                "gate_ref": "changes/c1/gate-output/1",
            }
        },
    }


def _review(output: bytes) -> dict[str, Any]:
    return {
        **REQUIREMENTS[1],
        "record": {
            "result": {
                "review_ref": "changes/c1/review-output/1.txt",
                "review_sha256": hashlib.sha256(output).hexdigest(),
            }
        },
    }


def _clean_review() -> dict[str, Any]:
    return {
        "class": "review-arch",
        "affected_point": "api",
        "criterion": "arch-ok",
        "divergences": [],
    }


def test_all_clean_assesses_every_id_and_has_no_findings() -> None:
    output = _review_output([_clean_review()])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert findings == []
    assert [(item["criterion"], item["state"]) for item in assessments] == [
        ("tests-pass", "no_divergence"),
        ("arch-ok", "no_divergence"),
    ]


def test_gate_failure_is_one_finding_per_non_zero_command() -> None:
    output = _review_output([_clean_review()])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "ruff",
                        "argv": ["ruff", "check"],
                        "exit_code": 1,
                        "timed_out": False,
                    },
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    },
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert len(findings) == 1
    assert findings[0]["source"] == "gate"
    assert findings[0]["detail"]["exit_code"] == 1
    assert assessments[0]["state"] == "divergent"


def test_gate_timeout_is_indeterminate_without_a_finding() -> None:
    output = _review_output([_clean_review()])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": None,
                        "timed_out": True,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert not any(item["source"] == "gate" for item in findings)
    assert assessments[0]["state"] == "indeterminate"


def test_review_divergence_and_unknown_association_are_recorded() -> None:
    output = _review_output(
        [
            {
                **_clean_review(),
                "divergences": [
                    {
                        "between": ["specification", "implementation"],
                        "description": "wrong API",
                    },
                    {
                        "between": ["validation", "affected_point"],
                        "description": "missing test",
                    },
                ],
            },
            {
                "class": "other",
                "affected_point": "api",
                "criterion": "unknown",
                "divergences": [
                    {
                        "between": ["implementation", "validation"],
                        "description": "unmapped",
                    }
                ],
            },
        ],
        [{"between": ["specification", "validation"], "description": "unassociated"}],
    )
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert len(findings) == 4
    assert sum(item["association"] == "requirement" for item in findings) == 2
    assert sum(item["association"] == "unknown" for item in findings) == 2
    assert assessments[1]["state"] == "divergent"


def test_partial_and_duplicate_review_entries_are_indeterminate_without_findings() -> (
    None
):
    output = _review_output([_clean_review(), _clean_review()])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert findings == []
    assert assessments[1]["state"] == "indeterminate"

    output = _review_output([])
    _, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert assessments[1]["state"] == "indeterminate"

    unknown = {
        "class": "other",
        "affected_point": "api",
        "criterion": "unknown",
        "divergences": [
            {
                "between": ["implementation", "validation"],
                "description": "unmapped",
            }
        ],
    }
    output = _review_output([unknown, unknown])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert not any(item["association"] == "unknown" for item in findings)
    assert assessments[1]["state"] == "indeterminate"


def test_unreadable_review_output_makes_review_evidence_indeterminate() -> None:
    output = b"canned review\n"
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert findings == []
    assert assessments[1]["state"] == "indeterminate"


def test_missing_evidence_or_invalid_attempt_is_not_assessed() -> None:
    output = _review_output([_clean_review()])
    _, assessments = derive_findings(REQUIREMENTS, "none", [], None)
    assert all(item["state"] == "not_assessed" for item in assessments)
    _, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {
                        "name": "pytest",
                        "argv": ["pytest"],
                        "exit_code": 0,
                        "timed_out": False,
                    }
                ]
            )
        ],
        output,
    )
    assert assessments[1]["state"] == "not_assessed"


def _assessment_payload(
    *,
    assessments: list[dict[str, Any]] | None = None,
    unassociated: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": REVIEW_ASSESSMENT_SCHEMA,
        "assessments": [] if assessments is None else assessments,
        "unassociated": [] if unassociated is None else unassociated,
    }


@pytest.mark.parametrize(
    "output",
    [
        b"canned review\n",
        f"{ASSESSMENT_BEGIN}\n{{}}\n{ASSESSMENT_END}\n".encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(_assessment_payload())
            + f"\n{ASSESSMENT_END}\n{ASSESSMENT_BEGIN}\n{{}}\n{ASSESSMENT_END}"
        ).encode(),
        f"{ASSESSMENT_BEGIN}\nnot json\n{ASSESSMENT_END}\n".encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                _assessment_payload(
                    unassociated=[
                        {
                            "between": ["implementation", "implementation"],
                            "description": "x",
                        }
                    ]
                )
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        b"".join(
            [
                ASSESSMENT_BEGIN.encode(),
                b"\n\xff\n",
                ASSESSMENT_END.encode(),
            ]
        ),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                {
                    **_assessment_payload(),
                    "assessments": [
                        {
                            "class": "review-arch",
                            "affected_point": "api",
                            "criterion": "arch-ok",
                            "divergences": [
                                {
                                    "between": ["specification", "implementation"],
                                    "description": "   ",
                                }
                            ],
                        }
                    ],
                }
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                {
                    **_assessment_payload(),
                    "unexpected": True,
                }
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            '{"schema":"profile-dev/review-assessment/1",'
            '"assessments":[],"assessments":[],"unassociated":[]}'
            f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                _assessment_payload(
                    unassociated=[
                        {
                            "between": ["specification", "implementation"],
                            "description": "x",
                            "extra": True,
                        }
                    ]
                )
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                _assessment_payload(
                    unassociated=[
                        {
                            "between": ["specification", "outside"],
                            "description": "x",
                        }
                    ]
                )
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                {
                    **_assessment_payload(),
                    "schema": "profile-dev/review-assessment/2",
                }
            )
            + f"\n{ASSESSMENT_END}"
        ).encode(),
        (
            f"{ASSESSMENT_BEGIN}\n"
            + '{"schema":"profile-dev/review-assessment/1",'
            + '"assessments":['
            + "[" * 1100
            + "]" * 1100
            + '],"unassociated":[]}'
            + f"\n{ASSESSMENT_END}"
        ).encode(),
    ],
)
def test_review_parser_rejects_unreadable_blocks(output: bytes) -> None:
    assert parse_review_assessment(output) is None


def test_review_parser_accepts_trailing_marker_whitespace() -> None:
    payload = json.dumps(_assessment_payload())
    output = (f"{ASSESSMENT_BEGIN}  \r\n{payload}\n{ASSESSMENT_END}\t \r\n").encode()
    assert parse_review_assessment(output) == _assessment_payload()


def test_review_parser_rejects_leading_marker_whitespace() -> None:
    payload = json.dumps(_assessment_payload())
    output = f"  {ASSESSMENT_BEGIN}\n{payload}\n{ASSESSMENT_END}\n".encode()
    assert parse_review_assessment(output) is None


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085"])
def test_review_parser_keeps_unicode_line_separators_inside_json_strings(
    separator: str,
) -> None:
    payload = _assessment_payload()
    payload["unassociated"] = [
        {
            "between": ["specification", "implementation"],
            "description": f"a{separator}b",
        }
    ]
    output = (
        f"{ASSESSMENT_BEGIN}\n"
        + json.dumps(payload, ensure_ascii=False)
        + f"\n{ASSESSMENT_END}\n"
    ).encode()
    assert parse_review_assessment(output) == payload


@pytest.mark.parametrize(
    ("commands", "finding_count", "state"),
    [
        (
            [
                {"name": "one", "argv": ["one"], "exit_code": 1, "timed_out": False},
                {"name": "two", "argv": ["two"], "exit_code": 2, "timed_out": False},
            ],
            2,
            "divergent",
        ),
        (
            [
                {
                    "name": "fail",
                    "argv": ["fail"],
                    "exit_code": 1,
                    "timed_out": False,
                },
                {
                    "name": "timeout",
                    "argv": ["timeout"],
                    "exit_code": None,
                    "timed_out": True,
                },
            ],
            1,
            "indeterminate",
        ),
        (
            [
                {
                    "name": "timeout",
                    "argv": ["timeout"],
                    "exit_code": None,
                    "timed_out": True,
                },
                {"name": "fail", "argv": ["fail"], "exit_code": 1, "timed_out": False},
            ],
            1,
            "indeterminate",
        ),
        (
            [{"name": "bool", "argv": ["bool"], "exit_code": True, "timed_out": False}],
            0,
            "indeterminate",
        ),
        (
            [{"name": "null", "argv": ["null"], "exit_code": None, "timed_out": False}],
            0,
            "indeterminate",
        ),
        ([], 0, "indeterminate"),
    ],
)
def test_gate_derivation_handles_each_command_independently(
    commands: list[dict[str, Any]], finding_count: int, state: str
) -> None:
    output = _review_output([_clean_review()])
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [_gate(commands), _review(output)],
        output,
    )
    gate_findings = [item for item in findings if item["source"] == "gate"]
    assert len(gate_findings) == finding_count
    assert assessments[0]["state"] == state


def test_gate_non_mapping_commands_and_non_list_commands_are_indeterminate() -> None:
    output = _review_output([_clean_review()])
    for commands in (["bad"], None):
        gate = _gate(commands)  # type: ignore[arg-type]
        _, assessments = derive_findings(
            REQUIREMENTS, "valid", [gate, _review(output)], output
        )
        assert assessments[0]["state"] == "indeterminate"


def test_review_digest_mismatch_is_indeterminate() -> None:
    output = _review_output([_clean_review()])
    review = _review(output)
    review["record"]["result"]["review_sha256"] = "0" * 64
    _, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [_gate([{"exit_code": 0, "timed_out": False}]), review],
        output,
    )
    assert assessments[1]["state"] == "indeterminate"


def test_indeterminate_attempt_makes_every_assessment_not_assessed() -> None:
    output = _review_output([_clean_review()])
    _, assessments = derive_findings(
        REQUIREMENTS,
        "indeterminate",
        [_gate([{"exit_code": 1, "timed_out": False}]), _review(output)],
        output,
    )
    assert all(item["state"] == "not_assessed" for item in assessments)


def test_review_entry_for_gate_requirement_keeps_requirement_association() -> None:
    output = _review_output(
        [
            {
                "class": "gate-unit",
                "affected_point": "api",
                "criterion": "tests-pass",
                "divergences": [
                    {
                        "between": ["implementation", "validation"],
                        "description": "gate-linked review finding",
                    }
                ],
            }
        ]
    )
    findings, _ = derive_findings(
        REQUIREMENTS,
        "valid",
        [_gate([{"exit_code": 0, "timed_out": False}]), _review(output)],
        output,
    )
    assert findings[-1]["association"] == "requirement"
    assert findings[-1]["kind"] == "gate"


def test_non_divergent_review_requirement_emits_no_review_finding() -> None:
    output = _review_output(
        [
            _clean_review(),
            {
                **_clean_review(),
                "divergences": [
                    {
                        "between": ["specification", "implementation"],
                        "description": "duplicate entry",
                    }
                ],
            },
        ]
    )
    findings, assessments = derive_findings(
        REQUIREMENTS,
        "valid",
        [_gate([{"exit_code": 0, "timed_out": False}]), _review(output)],
        output,
    )
    assert assessments[1]["state"] == "indeterminate"
    assert not any(item["source"] == "review" for item in findings)


def test_mixed_findings_are_sorted_deterministically() -> None:
    output = _review_output(
        [
            {
                **_clean_review(),
                "divergences": [
                    {
                        "between": ["specification", "implementation"],
                        "description": "review finding",
                    }
                ],
            }
        ],
        [{"between": ["specification", "validation"], "description": "unknown"}],
    )
    findings, _ = derive_findings(
        REQUIREMENTS,
        "valid",
        [
            _gate(
                [
                    {"name": "z", "argv": ["z"], "exit_code": 1, "timed_out": False},
                    {"name": "a", "argv": ["a"], "exit_code": 1, "timed_out": False},
                ]
            ),
            _review(output),
        ],
        output,
    )
    assert [
        (
            item["source"],
            item["association"],
            item["class"],
            item["detail"].get("command", item["detail"].get("description")),
        )
        for item in findings
    ] == [
        ("review", "unknown", None, "unknown"),
        ("gate", "requirement", "gate-unit", "a"),
        ("gate", "requirement", "gate-unit", "z"),
        ("review", "requirement", "review-arch", "review finding"),
    ]
