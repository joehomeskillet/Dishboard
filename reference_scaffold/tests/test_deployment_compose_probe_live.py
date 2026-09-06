from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
from uuid import uuid4

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
RUN_LIVE_COMPOSE_PROBE = os.getenv("RUN_LIVE_COMPOSE_PROBE") == "1"


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a docker command and return the result."""
    return subprocess.run(
        ["docker", *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def load_env_example() -> dict[str, str]:
    """Parse deployment/.env.example into a dict."""
    values: dict[str, str] = {}
    for raw_line in (DEPLOYMENT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def find_free_port() -> int:
    """Find a free port on 127.0.0.1 for APP_HOST_PORT."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def build_app_image(tmp_path: Path) -> str:
    """Build cached app image and return immutable sha256:<id>."""
    iidfile = tmp_path / "iidfile.txt"
    docker(
        "build",
        "--iidfile",
        str(iidfile),
        "--file",
        str(DEPLOYMENT / "Dockerfile"),
        str(ROOT),
        check=True,
    )
    image_id = iidfile.read_text(encoding="utf-8").strip()
    assert image_id.startswith("sha256:"), f"Invalid image ID: {image_id}"
    assert len(image_id) == 71, f"Invalid image ID length: {image_id}"  # sha256:<64 hex>
    return image_id


def generate_secrets() -> dict[str, str]:
    """Generate strong random secrets for compose."""
    return {
        "postgres_owner_password.txt": secrets.token_hex(32),
        "postgres_app_password.txt": secrets.token_hex(32),
        "postgres_backup_password.txt": secrets.token_hex(32),
        "postgres_auth_issuer_password.txt": secrets.token_hex(32),
        "flask_secret_key.txt": secrets.token_hex(32),
        "entra_client_secret.txt": "placeholder-entra-secret",
        "redis_password.txt": secrets.token_hex(32),
    }


def prepare_compose_workspace(tmp_path: Path, app_image: str) -> tuple[Path, str]:
    """Prepare isolated compose workspace in tmp_path.
    
    Returns tuple of (workspace_path, project_name).
    """
    workspace = tmp_path / "compose_ws"
    workspace.mkdir(exist_ok=True)
    
    project_name = f"dishboard-probe-{uuid4().hex[:12]}"
    
    # Copy docker-compose.yml
    compose_src = DEPLOYMENT / "docker-compose.yml"
    compose_dst = workspace / "docker-compose.yml"
    compose_config = yaml.safe_load(compose_src.read_text(encoding="utf-8"))
    # This create-only image probe needs no connectivity or host IPAM allocation.
    compose_config.pop("networks", None)
    for service in compose_config["services"].values():
        service.pop("networks", None)
        service["network_mode"] = "none"
    compose_dst.write_text(yaml.safe_dump(compose_config), encoding="utf-8")
    
    # Copy required shell scripts
    for script_name in ["redis-healthcheck.sh", "postgres-backup.sh", "postgres-restore-control.sh"]:
        src = DEPLOYMENT / script_name
        dst = workspace / script_name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        dst.chmod(0o755)
    
    # Prepare .env from .env.example
    env_values = load_env_example()
    env_values["APP_IMAGE"] = app_image
    env_values["APP_HOST_PORT"] = str(find_free_port())
    env_values["ENTRA_ENABLED"] = "false"
    env_values["LOCAL_AUTH_ENABLED"] = "true"
    
    env_file = workspace / ".env"
    env_lines = []
    for key, value in env_values.items():
        env_lines.append(f"{key}={value}")
    env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    
    # Create secrets directory and files
    secrets_dir = workspace / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    secret_values = generate_secrets()
    for secret_name, secret_value in secret_values.items():
        secret_file = secrets_dir / secret_name
        secret_file.write_text(f"{secret_value}\n", encoding="utf-8")
    
    return workspace, project_name


@pytest.mark.skipif(
    not RUN_LIVE_COMPOSE_PROBE,
    reason="set RUN_LIVE_COMPOSE_PROBE=1 to run the live compose probe test"
)
def test_compose_creates_app_from_local_immutable_image_with_pull_never(tmp_path: Path) -> None:
    """Prove that compose creates app from a local immutable image without building."""
    
    # 1. Build the probe image; a cached digest may also belong to another workload.
    app_image = build_app_image(tmp_path)
    print(f"\nBuilt probe image: {app_image}")
    
    # 2. Prepare isolated compose workspace
    workspace, project_name = prepare_compose_workspace(tmp_path, app_image)
    
    try:
        # 3a. Verify docker compose config resolves image correctly
        config_result = docker(
            "compose",
            "-p", project_name,
            "-f", str(workspace / "docker-compose.yml"),
            "config",
            check=True,
        )
        config_yaml = yaml.safe_load(config_result.stdout)
        assert config_yaml["services"]["app"]["image"] == app_image
        assert config_yaml["services"]["migrate"]["image"] == app_image
        assert not config_yaml.get("networks")
        assert all(service["network_mode"] == "none" for service in config_yaml["services"].values())
        print(f"✓ compose config resolved image to {app_image}")
        
        # 3b. Verify docker compose create with --pull never succeeds
        create_result = docker(
            "compose",
            "-p", project_name,
            "-f", str(workspace / "docker-compose.yml"),
            "create",
            "--pull", "never",
            "--no-build",
            "app",
            check=False,
        )
        assert create_result.returncode == 0, create_result.stderr
        print("✓ compose create --pull never succeeded")
        
        # Inspect the created app container; this probe does not start services.
        app_container_name = f"{project_name}-app-1"
        inspect_result = docker(
            "inspect",
            "--format", "{{.Image}}",
            app_container_name,
            check=True,
        )
        created_image = inspect_result.stdout.strip()
        assert created_image == app_image
        print(f"✓ created app container image is {created_image}")
        
        # 3c. Negative: verify compose create fails with non-existent image
        fake_image = "sha256:" + ("0" * 64)
        env_override = workspace / ".env"
        env_content = env_override.read_text(encoding="utf-8")
        env_content = env_content.replace(app_image, fake_image)
        env_override.write_text(env_content, encoding="utf-8")
        
        fail_result = docker(
            "compose",
            "-p", f"{project_name}-fail",
            "-f", str(workspace / "docker-compose.yml"),
            "create",
            "--pull", "never",
            "--no-build",
            "app",
            check=False,
        )
        assert fail_result.returncode != 0, "Expected create to fail with non-existent image"
        assert f"No such image: {fake_image}" in fail_result.stderr, "Expected explicit missing image error"
        print(f"✓ compose create failed because image is missing: {fake_image}")
        
    finally:
        cleanup = [docker(
            "compose", "-p", own_project,
            "-f", str(workspace / "docker-compose.yml"),
            "down", "--volumes", "--remove-orphans", check=False,
        ) for own_project in (project_name, f"{project_name}-fail")]
        assert all(result.returncode == 0 for result in cleanup), "Probe project cleanup failed"
        for own_project in (project_name, f"{project_name}-fail"):
            for resource, options in (("container", ("--all",)), ("network", ()), ("volume", ())):
                remaining = docker(resource, "ls", *options, "--quiet", "--filter",
                                   f"label=com.docker.compose.project={own_project}")
                assert not remaining.stdout.strip(), (own_project, resource, "cleanup incomplete")
        # Never delete image IDs: the build cache or other workloads may share them.
        print("✓ Both probe projects cleaned up; cached images retained")


@pytest.mark.parametrize("failure,cleanup_fails", [
    ("missing", False), ("network", False), ("wrong-image", False), ("missing", True),
])
def test_probe_requires_image_error_and_cleans_both_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, cleanup_fails: bool,
) -> None:
    """Reject unrelated failures and preserve cleanup even when verification fails."""
    app_image = "sha256:" + "1" * 64
    fake_image = "sha256:" + "0" * 64
    calls: list[tuple[str, ...]] = []

    def fake_docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        output, error, code = "", "", 0
        if "config" in arguments:
            output = yaml.safe_dump({"services": {
                name: {"image": app_image, "network_mode": "none"} for name in ("app", "migrate")}})
        elif arguments[0] == "inspect":
            output = app_image
        elif "create" in arguments and arguments[2].endswith("-fail"):
            error = {"missing": f"Error response from daemon: No such image: {fake_image}",
                     "network": "invalid pool request: Pool overlaps with other one on this address space",
                     "wrong-image": "Error response from daemon: No such image: unrelated"}[failure]
            code = 1
        elif "down" in arguments and cleanup_fails and not arguments[2].endswith("-fail"):
            code = 1
        return subprocess.CompletedProcess(arguments, code, output, error)

    monkeypatch.setattr(f"{__name__}.docker", fake_docker)
    monkeypatch.setattr(f"{__name__}.build_app_image", lambda _path: app_image)
    if failure != "missing" or cleanup_fails:
        with pytest.raises(AssertionError, match="cleanup failed" if cleanup_fails else "missing image error"):
            test_compose_creates_app_from_local_immutable_image_with_pull_never(tmp_path)
    else:
        test_compose_creates_app_from_local_immutable_image_with_pull_never(tmp_path)
    projects = [arguments[2] for arguments in calls if "down" in arguments]
    assert len(projects) == 2 and projects[1] == projects[0] + "-fail"
    assert all(arguments[:2] != ("image", "rm") for arguments in calls)
    if not cleanup_fails:
        assert sum("--quiet" in arguments for arguments in calls) == 6
