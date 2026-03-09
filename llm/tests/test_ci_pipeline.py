from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml  # type: ignore[import-untyped]

from llm import run_ci_suite, run_quality_gate


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def _load_workflow(filename: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / filename).read_text(encoding="utf-8"))


def _step_named(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"Step {name!r} not found")


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_ci_workflow_includes_required_gates():
    workflow = _load_workflow("fly-deploy.yml")
    jobs = workflow["jobs"]

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["env"] == {
        "APP_IMAGE_NAME": "cyberchesscoach",
        "API_IMAGE_NAME": "cyberchesscoach-llm-api",
    }
    assert workflow["concurrency"] == {
        "group": "ci-cd-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }
    assert {
        "workflow-lint",
        "python-tests",
        "python-quality",
        "dependency-security",
        "node-security",
        "docker-images",
        "image-security",
        "deploy",
        "release",
    }.issubset(jobs)
    assert set(jobs["docker-images"]["needs"]) == {
        "workflow-lint",
        "python-tests",
        "python-quality",
        "dependency-security",
        "node-security",
    }
    assert "image-security" in jobs["deploy"]["needs"]
    assert "image-security" in jobs["release"]["needs"]
    assert jobs["deploy"]["environment"] == {"name": "production"}
    assert jobs["deploy"]["permissions"] == {"contents": "read"}
    assert jobs["release"]["permissions"] == {"contents": "write"}


def test_ci_workflow_hardens_checkout_and_supply_chain_controls():
    workflow = _load_workflow("fly-deploy.yml")
    jobs = workflow["jobs"]

    for job_name in [
        "workflow-lint",
        "python-tests",
        "python-quality",
        "dependency-security",
        "node-security",
        "docker-images",
        "deploy",
    ]:
        checkout = _step_named(jobs[job_name], "Checkout repository")
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["persist-credentials"] is False

    assert (
        _step_named(jobs["workflow-lint"], "Lint GitHub Actions workflows")["uses"]
        == "raven-actions/actionlint@v2"
    )
    assert (
        _step_named(jobs["node-security"], "Audit Node dependencies")["run"]
        == "npm audit --omit=dev --audit-level=high"
    )
    docker_job = jobs["docker-images"]
    assert docker_job["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
        "attestations": "write",
    }
    assert docker_job["outputs"] == {
        "image_owner": "${{ steps.prep.outputs.owner }}",
        "app_digest": "${{ steps.build-app.outputs.digest }}",
        "api_digest": "${{ steps.build-api.outputs.digest }}",
    }
    assert _step_named(docker_job, "Build app image")["with"]["provenance"] == (
        "${{ github.event_name == 'push' }}"
    )
    assert _step_named(docker_job, "Build app image")["with"]["sbom"] == (
        "${{ github.event_name == 'push' }}"
    )
    assert _step_named(docker_job, "Build llm API image")["with"]["provenance"] == (
        "${{ github.event_name == 'push' }}"
    )
    assert _step_named(docker_job, "Build llm API image")["with"]["sbom"] == (
        "${{ github.event_name == 'push' }}"
    )
    assert _step_named(docker_job, "Install Cosign")["uses"] == "sigstore/cosign-installer@v3"
    assert [
        step["uses"]
        for step in docker_job["steps"]
        if step.get("uses") == "actions/attest-build-provenance@v2"
    ] == [
        "actions/attest-build-provenance@v2",
        "actions/attest-build-provenance@v2",
    ]

    image_security = jobs["image-security"]
    assert image_security["permissions"] == {
        "contents": "read",
        "packages": "read",
        "security-events": "write",
    }
    scan_app = _step_named(image_security, "Scan published app image")
    assert scan_app["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert scan_app["with"]["scan-type"] == "image"
    assert scan_app["with"]["format"] == "table"
    assert scan_app["with"]["vuln-type"] == "library"

    sarif_app = _step_named(image_security, "Generate app image SARIF")
    assert sarif_app["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert sarif_app["with"]["format"] == "sarif"
    assert sarif_app["with"]["exit-code"] == "0"

    scan_api = _step_named(image_security, "Scan published llm API image")
    assert scan_api["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert scan_api["with"]["scan-type"] == "image"
    assert scan_api["with"]["format"] == "table"
    assert scan_api["with"]["vuln-type"] == "os,library"

    sarif_api = _step_named(image_security, "Generate llm API image SARIF")
    assert sarif_api["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert sarif_api["with"]["format"] == "sarif"
    assert sarif_api["with"]["exit-code"] == "0"


def test_security_workflow_uses_safe_checkout_and_codeql_v4():
    workflow = _load_workflow("security.yml")
    jobs = workflow["jobs"]

    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }

    for job in jobs.values():
        checkout = _step_named(job, "Checkout repository")
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["persist-credentials"] is False

    codeql_python_job = jobs["codeql-python"]
    assert (
        _step_named(codeql_python_job, "Initialize CodeQL")["uses"]
        == "github/codeql-action/init@v4"
    )
    assert _step_named(codeql_python_job, "Initialize CodeQL")["with"]["languages"] == "python"
    assert (
        _step_named(codeql_python_job, "Analyze with CodeQL")["uses"]
        == "github/codeql-action/analyze@v4"
    )

    codeql_javascript_job = jobs["codeql-javascript"]
    assert "schedule" in codeql_javascript_job["if"]
    assert "workflow_dispatch" in codeql_javascript_job["if"]
    assert (
        _step_named(codeql_javascript_job, "Initialize CodeQL")["with"]["languages"] == "javascript"
    )

    trivy_misconfig_job = jobs["trivy-misconfig"]
    assert (
        trivy_misconfig_job["if"]
        == "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    )
    assert (
        _step_named(trivy_misconfig_job, "Run Trivy misconfiguration scan")["with"]["scanners"]
        == "misconfig"
    )
    assert (
        _step_named(trivy_misconfig_job, "Run Trivy misconfiguration scan")["uses"]
        == "aquasecurity/trivy-action@0.34.0"
    )

    trivy_runtime_job = jobs["trivy-runtime-vulns"]
    assert (
        trivy_runtime_job["if"]
        == "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    )
    prepare_trivy_input = _step_named(
        trivy_runtime_job, "Prepare Trivy runtime manifest scan input"
    )
    assert (
        "cp llm/requirements.txt tmp_logs/trivy-runtime/requirements.txt"
        in prepare_trivy_input["run"]
    )
    trivy_runtime_step = _step_named(trivy_runtime_job, "Run Trivy runtime vulnerability scan")
    assert trivy_runtime_step["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert trivy_runtime_step["with"]["scanners"] == "vuln"
    assert trivy_runtime_step["with"]["scan-ref"] == "tmp_logs/trivy-runtime"
    assert trivy_runtime_step["with"]["format"] == "table"


def test_container_images_keep_health_checks_and_non_root_runtime():
    root_dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV NODE_ENV=production" in root_dockerfile
    assert "FROM node:22-alpine AS deps" in root_dockerfile
    assert "FROM gcr.io/distroless/nodejs22-debian12:nonroot" in root_dockerfile
    assert "RUN apk upgrade --no-cache" in root_dockerfile
    assert "COPY --chown=nonroot:nonroot llm/server.js ./server.js" in root_dockerfile
    assert (
        "COPY --from=deps --chown=nonroot:nonroot /app/node_modules ./node_modules"
        in root_dockerfile
    )
    assert "COPY llm/. ." not in root_dockerfile
    assert 'CMD ["server.js"]' in root_dockerfile
    assert "HEALTHCHECK" in root_dockerfile
    assert "/nodejs/bin/node" in root_dockerfile
    assert "/health" in root_dockerfile

    llm_api_dockerfile = (ROOT / "llm" / "Dockerfile.api").read_text(encoding="utf-8")
    assert "apt-get upgrade -y" in llm_api_dockerfile
    assert (
        "rm -rf /app/llm/tests /app/llm/rag/tests /app/llm/.github /app/llm/redis-win"
        in llm_api_dockerfile
    )
    assert (
        "rm -f /app/llm/package.json /app/llm/package-lock.json /app/llm/server.js"
        in llm_api_dockerfile
    )
    assert "USER appuser" in llm_api_dockerfile
    assert "HEALTHCHECK" in llm_api_dockerfile
    assert "127.0.0.1:8000/health" in llm_api_dockerfile

    llm_dockerfile = (ROOT / "llm" / "Dockerfile").read_text(encoding="utf-8")
    assert "rm -rf /app/tests /app/rag/tests /app/.github /app/redis-win" in llm_dockerfile
    assert "rm -f /app/package.json /app/package-lock.json /app/server.js" in llm_dockerfile
    assert "USER appuser" in llm_dockerfile
    assert "HEALTHCHECK" in llm_dockerfile
    assert "127.0.0.1:8000/health" in llm_dockerfile

    node_server = (ROOT / "llm" / "server.js").read_text(encoding="utf-8")
    assert 'app.get("/health"' in node_server


def test_runtime_dependency_files_are_pinned():
    requirements = (ROOT / "llm" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pinned_requirements = [
        line for line in requirements if line.strip() and not line.startswith("#")
    ]

    assert pinned_requirements
    assert all("==" in line for line in pinned_requirements)

    package_json = json.loads((ROOT / "llm" / "package.json").read_text(encoding="utf-8"))
    dependencies = package_json["dependencies"]

    assert dependencies
    assert all(not version.startswith(("^", "~")) for version in dependencies.values())
    assert _version_tuple(dependencies["express"]) >= (4, 22, 1)
    assert "node-fetch" not in dependencies


def test_run_ci_suite_builds_expected_pytest_command(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []

    def _fake_run(cmd: list[str], cwd: Path, check: bool):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check})
        return SimpleNamespace(returncode=7)

    artifact_dir = tmp_path / "tmp_logs"
    monkeypatch.setattr(run_ci_suite, "ARTIFACT_DIR", artifact_dir)
    monkeypatch.setattr(run_ci_suite.subprocess, "run", _fake_run)

    assert run_ci_suite.main() == 7
    assert artifact_dir.is_dir()
    assert calls == [
        {
            "cmd": [
                run_ci_suite.sys.executable,
                "-m",
                "pytest",
                "-q",
                *run_ci_suite.TEST_TARGETS,
                *[f"--cov={target}" for target in run_ci_suite.COVERAGE_TARGETS],
                "--cov-report=term-missing:skip-covered",
                "--cov-report=xml:tmp_logs/coverage.xml",
                "--cov-fail-under=80",
                "--junitxml=tmp_logs/pytest-ci.xml",
            ],
            "cwd": run_ci_suite.PROJECT_ROOT,
            "check": False,
        }
    ]
    assert "llm/tests/test_ci_pipeline.py" in run_ci_suite.TEST_TARGETS


def test_run_quality_gate_runs_all_steps_by_default(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []

    def _fake_run(
        cmd: list[str],
        cwd: Path,
        check: bool,
        env: dict[str, str] | None = None,
    ):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env})
        return SimpleNamespace(returncode=0)

    pylint_home = tmp_path / ".pylint"
    monkeypatch.setattr(run_quality_gate, "PYLINT_HOME", pylint_home)
    monkeypatch.setattr(run_quality_gate.subprocess, "run", _fake_run)
    monkeypatch.setattr(run_quality_gate.sys, "argv", ["run_quality_gate.py"])

    assert run_quality_gate.main() == 0
    assert [call["cmd"][2] for call in calls] == ["black", "pylint", "mypy"]
    assert all(call["cwd"] == run_quality_gate.PROJECT_ROOT for call in calls)
    assert all(call["check"] is False for call in calls)
    assert calls[0]["env"] is None
    assert calls[1]["env"]["PYLINTHOME"] == str(pylint_home)
    assert calls[2]["env"] is None
    assert pylint_home.is_dir()


def test_run_quality_gate_runs_only_requested_steps(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def _fake_run(
        cmd: list[str],
        cwd: Path,
        check: bool,
        env: dict[str, str] | None = None,
    ):
        del cwd, check, env
        calls.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_quality_gate, "PYLINT_HOME", tmp_path / ".pylint")
    monkeypatch.setattr(run_quality_gate.subprocess, "run", _fake_run)
    monkeypatch.setattr(run_quality_gate.sys, "argv", ["run_quality_gate.py", "black", "mypy"])

    assert run_quality_gate.main() == 0
    assert [call[2] for call in calls] == ["black", "mypy"]


def test_run_quality_gate_rejects_unknown_steps(monkeypatch):
    monkeypatch.setattr(run_quality_gate.sys, "argv", ["run_quality_gate.py", "ruff"])

    with pytest.raises(SystemExit) as excinfo:
        run_quality_gate.main()

    assert excinfo.value.code == 2
