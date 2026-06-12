"""Integration tests for deploy-agent-engine-kit — requires live ADC + GCP project.

Run manually:
    cd repo/kits/deploy-agent-engine-kit
    python -m pytest tests/integration/ -m integration -v

Requires:
    - gcloud auth application-default login
    - GOOGLE_CLOUD_PROJECT set (or defaults to your-project-id)
    - STAGING_BUCKET set (or defaults to gs://beddel-workflows)
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def flow_path() -> Path:
    """Path to the sum-two-numbers.yaml bundled flow."""
    p = Path(__file__).resolve().parents[5] / "src" / "beddel-py" / "src" / "beddel" / "flows" / "sum-two-numbers.yaml"
    if not p.exists():
        pytest.skip(f"Flow file not found: {p}")
    return p


class TestDeployLive:
    """Live integration tests — deploys to real Agent Engine."""

    def test_deploy_and_query(self, flow_path: Path) -> None:
        """Deploy sum-two-numbers flow, verify query works, then cleanup."""
        from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

        # Deploy
        result = deploy_flow_to_agent_engine(flow_path=flow_path)

        assert result.resource_name
        assert "your-project-id" in result.project or result.project
        assert result.console_url.startswith("https://")

        # Query the deployed agent
        try:
            import vertexai
            from vertexai import agent_engines

            vertexai.init(
                project=result.project,
                location=result.region,
            )

            remote_app = agent_engines.get(result.resource_name)
            session = remote_app.create_session(user_id="integration-test")

            responses = []
            for event in remote_app.stream_query(
                user_id="integration-test",
                session_id=session["id"],
                message="Sum 3 and 7",
            ):
                if hasattr(event, "content") and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            responses.append(part.text)

            assert len(responses) > 0, "Agent should have responded"

        finally:
            # Cleanup: delete the deployed agent
            try:
                remote_app = agent_engines.get(result.resource_name)
                remote_app.delete()
            except Exception:
                pass  # Best-effort cleanup
