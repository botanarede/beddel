"""AC3: Verdict parity for component and shared-contract Changes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from beddel_profile_dev import _adapters
from beddel_profile_dev import config as cfg
from beddel_profile_dev._io import records_root
from beddel_profile_dev.findings import (
    ASSESSMENT_BEGIN,
    ASSESSMENT_END,
    REVIEW_ASSESSMENT_SCHEMA,
)
from beddel_profile_dev.tools.attempt import profile_open_attempt
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.evidence import profile_capture_evidence
from beddel_profile_dev.tools.gate import profile_run_gate
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.report import profile_record_report
from beddel_profile_dev.tools.review import profile_run_review

from ._helpers import FakeReviewAdapter, change_fixture, good, stub_gate_tools


@pytest.mark.parametrize(
    "touched, affected_kind",
    [("src/api.py", "component"), ("src/contracts.yaml", "shared_contract")],
)
@pytest.mark.parametrize(
    "mypy_exit, expected_verdict", [(0, "consistent"), (1, "has pendency")]
)
def test_verdict_is_parity_stable_for_component_and_contract_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    touched: str,
    affected_kind: str,
    mypy_exit: int,
    expected_verdict: str,
) -> None:
    data = good()
    for criterion in data["criteria"]:
        criterion["blocking"] = True
    repo, base, revision = change_fixture(
        tmp_path,
        lambda path: (path / touched).write_text(
            "x = 2\n" if touched.endswith(".py") else "a: 2\n"
        ),
        data=data,
    )
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)

    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("mypy", "."),))
    monkeypatch.setattr(cfg, "GATE_TOTAL_TIMEOUT_SECONDS", None)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("STUB_EXIT_MYPY", str(mypy_exit))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    review_output = (
        f"{ASSESSMENT_BEGIN}\n"
        + json.dumps(
            {
                "schema": REVIEW_ASSESSMENT_SCHEMA,
                "assessments": [
                    {
                        "class": "review-arch",
                        "affected_point": "api",
                        "criterion": "arch-ok",
                        "divergences": [],
                    }
                ],
                "unassociated": [],
            },
            separators=(",", ":"),
        )
        + f"\n{ASSESSMENT_END}\n"
    )
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=review_output
        ),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    profile_capture_evidence(str(repo), "c1", revision, attempt)
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )

    points = report["items"]["affected_points"]["value"]
    assert [point["kind"] for point in points] == [affected_kind]
    assert [point["id"] for point in points] == [
        "api" if affected_kind == "component" else "contracts"
    ]
    assert report["verdict"] == expected_verdict
    reasons = {
        item["reason"] for item in report["items"]["pendencies"].get("value", [])
    }
    assert reasons == (set() if mypy_exit == 0 else {"finding_blocking"})
