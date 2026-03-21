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
        "android-build",
        "compose-validate",
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
        "android-build",
        "compose-validate",
    }
    assert "image-security" in jobs["deploy"]["needs"]
    assert "image-security" in jobs["release"]["needs"]
    assert jobs["deploy"]["environment"] == {"name": "production"}
    assert jobs["deploy"]["permissions"] == {"contents": "read"}
    assert jobs["release"]["permissions"] == {"contents": "write"}


def test_ci_workflow_hardens_checkout_and_supply_chain_controls():  # pylint: disable=too-many-statements
    workflow = _load_workflow("fly-deploy.yml")
    jobs = workflow["jobs"]

    for job_name in [
        "workflow-lint",
        "python-tests",
        "python-quality",
        "dependency-security",
        "node-security",
        "android-build",
        "compose-validate",
        "docker-images",
        "image-security",
        "deploy",
    ]:
        checkout = _step_named(jobs[job_name], "Checkout repository")
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["persist-credentials"] is False

    android_build = jobs["android-build"]
    assert android_build["env"] == {
        "GRADLE_USER_HOME": "${{ github.workspace }}/.gradle",
        "ANDROID_USER_HOME": "${{ github.workspace }}/.android",
    }
    android_test_step = _step_named(android_build, "Run Android host JVM unit tests")
    assert android_test_step["working-directory"] == "android"
    assert android_test_step["run"] == "./gradlew test --no-daemon"

    android_manifest_step = _step_named(android_build, "Generate and validate packaged manifests")
    assert android_manifest_step["working-directory"] == "android"
    assert (
        android_manifest_step["run"]
        == "./gradlew processDebugManifestForPackage processReleaseManifestForPackage --no-daemon"
    )
    verify_manifest_step = _step_named(
        android_build, "Verify packaged manifest includes INTERNET permission"
    )
    assert verify_manifest_step["shell"] == "bash"
    assert "android.permission.INTERNET" in verify_manifest_step["run"]
    assert "processDebugManifestForPackage/AndroidManifest.xml" in verify_manifest_step["run"]
    assert "processReleaseManifestForPackage/AndroidManifest.xml" in verify_manifest_step["run"]

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
    docker_login = _step_named(docker_job, "Log in to GHCR")
    assert docker_login["with"]["username"] == "${{ github.repository_owner }}"

    build_app = _step_named(docker_job, "Build app image")
    assert build_app["with"]["provenance"] is False
    assert build_app["with"]["sbom"] is False
    assert build_app["with"]["build-args"] == "BUILDDATE=${{ github.run_id }}"

    build_api = _step_named(docker_job, "Build llm API image")
    assert build_api["with"]["provenance"] is False
    assert build_api["with"]["sbom"] is False
    assert build_api["with"]["build-args"] == "BUILDDATE=${{ github.run_id }}"
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
    image_security_login = _step_named(image_security, "Log in to GHCR")
    assert image_security_login["with"]["username"] == "${{ github.repository_owner }}"

    scan_app = _step_named(image_security, "Scan published app image")
    assert scan_app["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert scan_app["with"]["scan-type"] == "image"
    assert scan_app["with"]["format"] == "table"
    assert scan_app["with"]["vuln-type"] == "library"
    assert scan_app["with"]["severity"] == "CRITICAL"
    assert scan_app["with"]["ignore-unfixed"] is True
    assert scan_app["with"]["trivy-config"] == "trivy.yaml"
    assert scan_app["env"]["TRIVY_CACHE_DIR"] == "${{ runner.temp }}/trivy"
    assert scan_app["env"]["TRIVY_TIMEOUT"] == "15m"
    assert scan_app["env"]["TRIVY_USERNAME"] == "${{ github.repository_owner }}"

    sarif_app = _step_named(image_security, "Generate app image SARIF")
    assert sarif_app["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert sarif_app["with"]["format"] == "sarif"
    assert sarif_app["with"]["exit-code"] == "0"
    assert sarif_app["with"]["ignore-unfixed"] is False
    assert sarif_app["with"]["trivy-config"] == "trivy.yaml"
    assert sarif_app["env"]["TRIVY_SKIP_DB_UPDATE"] == "true"
    assert sarif_app["env"]["TRIVY_USERNAME"] == "${{ github.repository_owner }}"

    scan_api = _step_named(image_security, "Scan published llm API image")
    assert scan_api["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert scan_api["with"]["scan-type"] == "image"
    assert scan_api["with"]["format"] == "table"
    assert scan_api["with"]["vuln-type"] == "os,library"
    assert scan_api["with"]["severity"] == "CRITICAL"
    assert scan_api["with"]["ignore-unfixed"] is True
    assert scan_api["with"]["trivy-config"] == "trivy.yaml"
    assert scan_api["env"]["TRIVY_TIMEOUT"] == "15m"
    assert scan_api["env"]["TRIVY_USERNAME"] == "${{ github.repository_owner }}"

    sarif_api = _step_named(image_security, "Generate llm API image SARIF")
    assert sarif_api["uses"] == "aquasecurity/trivy-action@0.34.0"
    assert sarif_api["with"]["format"] == "sarif"
    assert sarif_api["with"]["exit-code"] == "0"
    assert sarif_api["with"]["ignore-unfixed"] is False
    assert sarif_api["with"]["trivy-config"] == "trivy.yaml"
    assert sarif_api["env"]["TRIVY_SKIP_DB_UPDATE"] == "true"
    assert sarif_api["env"]["TRIVY_USERNAME"] == "${{ github.repository_owner }}"


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
    assert "github.event_name == 'schedule'" in trivy_misconfig_job["if"]
    assert "github.event_name == 'workflow_dispatch'" in trivy_misconfig_job["if"]
    assert "github.event_name == 'pull_request'" in trivy_misconfig_job["if"]
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
    assert "llm/tests/test_api_contract_validation.py" in run_ci_suite.TEST_TARGETS
    assert "llm/tests/test_coaching_pipeline_regression.py" in run_ci_suite.TEST_TARGETS
    assert "llm/tests/test_explain_schema_validation.py" in run_ci_suite.TEST_TARGETS


def test_python_tests_job_includes_mandatory_explicit_steps():
    """Verify the python-tests CI job has explicit named steps for each mandatory test category.

    TESTING.md CI Policy requires these to be distinct named steps so failures are
    immediately visible in the GitHub Actions UI rather than buried in the full suite log.
    """
    workflow = _load_workflow("fly-deploy.yml")
    python_tests_job = workflow["jobs"]["python-tests"]

    golden_step = _step_named(python_tests_job, "Run golden tests (Category A — mandatory)")
    assert "test_retriever.py" in golden_step["run"]
    assert "test_prompt_snapshot.py" in golden_step["run"]

    contract_step = _step_named(python_tests_job, "Run LLM contract tests (Category B — mandatory)")
    assert "test_fake_llm.py" in contract_step["run"]

    api_contract_step = _step_named(python_tests_job, "Run API contract validation")
    assert "test_api_contract_validation.py" in api_contract_step["run"]

    regression_step = _step_named(python_tests_job, "Run coaching pipeline regression tests")
    assert "test_coaching_pipeline_regression.py" in regression_step["run"]

    schema_step = _step_named(python_tests_job, "Run explain schema validation tests")
    assert "test_explain_schema_validation.py" in schema_step["run"]

    engine_regression_step = _step_named(python_tests_job, "Run engine regression tests")
    assert "test_engine_eval_benchmark.py" in engine_regression_step["run"]
    assert "test_engine_eval_lru_cache.py" in engine_regression_step["run"]

    api_security_step = _step_named(python_tests_job, "Run API security tests")
    assert "test_api_security.py" in api_security_step["run"]

    regression_pipeline_step = _step_named(python_tests_job, "Run regression pipeline")
    assert "run_regression_suite.py" in regression_pipeline_step["run"]

    # Full suite with coverage must still follow as the authoritative CI gate
    suite_step = _step_named(python_tests_job, "Run pytest suite with coverage")
    assert "run_ci_suite.py" in suite_step["run"]

    # Ordering: explicit category steps must precede the full suite
    step_names = [step.get("name") for step in python_tests_job["steps"]]
    golden_idx = step_names.index("Run golden tests (Category A — mandatory)")
    engine_regression_idx = step_names.index("Run engine regression tests")
    regression_pipeline_idx = step_names.index("Run regression pipeline")
    suite_idx = step_names.index("Run pytest suite with coverage")
    assert golden_idx < suite_idx, "Category A golden tests must run before the full suite"
    assert (
        engine_regression_idx < suite_idx
    ), "Engine regression tests must run before the full suite"
    assert regression_pipeline_idx < suite_idx, "Regression pipeline must run before the full suite"


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


# ---------------------------------------------------------------------------
# Phase 3 — Android release build integration
# ---------------------------------------------------------------------------


def test_android_build_job_apk_step_uses_vars_not_secrets():
    """COACH_API_BASE is visible in the APK binary — must be vars.*, not secrets.*.
    COACH_API_KEY is a rate-limit shield only and is appropriately secrets.*.
    The upload step must target the unsigned release APK path.
    """
    workflow = _load_workflow("fly-deploy.yml")
    android_build = workflow["jobs"]["android-build"]

    apk_step = _step_named(android_build, "Build release APK")
    assert apk_step["working-directory"] == "android"
    assert apk_step["run"] == "./gradlew assembleRelease --no-daemon"

    api_base_ref = apk_step["env"]["COACH_API_BASE"]
    assert "vars.COACH_API_BASE" in api_base_ref, (
        "COACH_API_BASE is visible in the APK; use vars.COACH_API_BASE (not secrets.*)"
    )
    assert "secrets.COACH_API_BASE" not in api_base_ref

    assert "secrets.COACH_API_KEY" in apk_step["env"]["COACH_API_KEY"]

    upload_step = _step_named(android_build, "Upload release APK")
    assert upload_step["with"]["path"].endswith("app-release-unsigned.apk")
    assert upload_step["uses"].startswith("actions/upload-artifact@")


def test_build_gradle_kts_release_enforces_https_and_obfuscation():
    """Release build must enable R8, shrink resources, and hard-fail on plain-HTTP
    COACH_API_BASE so a misconfigured secret is caught at build time, not at runtime.
    """
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")

    assert "isMinifyEnabled = true" in gradle, "R8 minification must be enabled for release"
    assert "isShrinkResources = true" in gradle, "Resource shrinking must be enabled for release"
    assert "proguard-android-optimize.txt" in gradle
    assert "proguard-rules.pro" in gradle

    assert 'startsWith("https://")' in gradle, (
        "Release build must hard-fail when COACH_API_BASE does not start with https://"
    )
    assert "error(" in gradle, "Hard-fail guard for non-HTTPS COACH_API_BASE must be present"

    assert 'System.getenv("COACH_API_BASE")' in gradle
    assert 'System.getenv("COACH_API_KEY")' in gradle


def test_build_gradle_kts_debug_reads_api_endpoint_from_env():
    """Debug builds must override the defaultConfig API endpoint from env vars so
    developers can test against Hetzner without modifying source code (Step 3.4).
    """
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")

    # Must appear in both release and debug blocks — count must be >= 2
    assert gradle.count('System.getenv("COACH_API_BASE")') >= 2, (
        "COACH_API_BASE env-var override must appear in both debug and release build types"
    )
    assert gradle.count('System.getenv("COACH_API_KEY")') >= 2, (
        "COACH_API_KEY env-var override must appear in both debug and release build types"
    )


def test_proguard_rules_preserve_api_model_classes():
    """ProGuard/R8 must not rename or remove API model members accessed by string
    name through org.json, Kotlin coroutine internals, or EncryptedSharedPreferences.
    """
    proguard = (ROOT / "android" / "app" / "proguard-rules.pro").read_text(encoding="utf-8")

    assert "-keepattributes SourceFile,LineNumberTable" in proguard, (
        "Stack-trace line numbers must be preserved for crash reporting"
    )
    assert "com.example.myapplication" in proguard, (
        "API model classes in com.example.myapplication must be kept"
    )
    assert "public *" in proguard, (
        "Public members of model classes must be kept for org.json field access"
    )
    assert "kotlinx.coroutines" in proguard, (
        "Kotlin coroutine internals must be preserved"
    )
    assert "androidx.security.crypto" in proguard, (
        "AndroidX EncryptedSharedPreferences must be preserved"
    )


# ---------------------------------------------------------------------------
# Phase 4 — Hetzner deploy and Phase 5 — runtime configuration
# ---------------------------------------------------------------------------


def test_hetzner_deploy_health_gates_rollout():
    """The deploy script must: use set -euo pipefail, pull before restart, perform
    a zero-downtime --no-deps restart, and poll /health before declaring success.
    """
    workflow = _load_workflow("fly-deploy.yml")
    deploy = workflow["jobs"]["deploy"]

    assert deploy["environment"] == {"name": "production"}
    assert deploy["concurrency"]["group"] == "hetzner-production"
    assert deploy["concurrency"]["cancel-in-progress"] is False

    ssh_step = _step_named(deploy, "Deploy to Hetzner via SSH")
    assert ssh_step["uses"] == "appleboy/ssh-action@v1.2.0"
    script: str = ssh_step["with"]["script"]

    assert "set -euo pipefail" in script, "SSH script must use strict error handling"
    assert "pull api" in script, "Must pull the new image before restarting"
    assert "up -d --no-deps api" in script, "Must do a zero-downtime --no-deps restart"
    assert "/health" in script, "Must poll /health to gate a successful rollout"
    assert "curl" in script


def test_docker_compose_prod_health_and_immutable_image():
    """Production compose must: pull a pre-built image (not build from source),
    expose api internally only, gate Caddy startup on api health, and rotate logs.
    """
    compose = yaml.safe_load(
        (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )

    api = compose["services"]["api"]

    assert "image" in api, "api must pull a pre-built image in prod, not build from source"
    assert "build" not in api, "api must not build from source in prod"
    assert "ports" not in api, "api must not publish ports to host — Caddy proxies it"
    assert "expose" in api

    assert "healthcheck" in api
    assert "/health" in str(api["healthcheck"]["test"])

    caddy = compose["services"]["caddy"]
    caddy_api_dep = caddy["depends_on"]["api"]
    assert caddy_api_dep.get("condition") == "service_healthy", (
        "Caddy must wait for api service_healthy before starting"
    )

    assert "logging" in api
    assert api["logging"]["driver"] == "json-file"
