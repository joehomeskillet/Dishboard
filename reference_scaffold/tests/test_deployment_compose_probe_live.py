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
    """Build throwaway app image and return immutable sha256:<id>."""
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
    compose_dst.write_text(compose_src.read_text(encoding="utf-8"), encoding="utf-8")
    
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
    
    # Create override compose file to disable specific network config and move to 10.x.x.0/24
    # to avoid collision with 172.31.213.0/24
    override_compose = {
        "networks": {
            "cafeteria_internal": {
                "driver": "bridge",
                "ipam": {
                    "driver": "default",
                    "config": [
                        {
                            "subnet": "10.255.255.0/24",
                            "gateway": "10.255.255.1",
                        }
                    ]
                },
            }
        },
        "services": {
            "app": {
                "networks": {
                    "cafeteria_internal": {
                        "ipv4_address": "10.255.255.20"
                    }
                }
            }
        },
    }
    override_file = workspace / "override.yml"
    override_file.write_text(
        yaml.dump(override_compose, default_flow_style=False),
        encoding="utf-8",
    )
    
    return workspace, project_name


@pytest.mark.skipif(
    not RUN_LIVE_COMPOSE_PROBE,
    reason="set RUN_LIVE_COMPOSE_PROBE=1 to run the live compose probe test"
)
def test_compose_creates_app_from_local_immutable_image_with_pull_never(tmp_path: Path) -> None:
    """Prove that docker compose starts app from local immutable image id without build."""
    
    # 1. Build throwaway app image
    app_image = build_app_image(tmp_path)
    print(f"\nBuilt throwaway image: {app_image}")
    
    # Snapshot images before probe
    images_before = set(docker("images", "-q").stdout.strip().split("\n"))
    images_before.discard("")
    
    # 2. Prepare isolated compose workspace
    workspace, project_name = prepare_compose_workspace(tmp_path, app_image)
    
    try:
        # 3a. Verify docker compose config resolves image correctly
        config_result = docker(
            "compose",
            "-p", project_name,
            "-f", str(workspace / "docker-compose.yml"),
            "-f", str(workspace / "override.yml"),
            "config",
            check=True,
        )
        config_yaml = yaml.safe_load(config_result.stdout)
        assert config_yaml["services"]["app"]["image"] == app_image
        assert config_yaml["services"]["migrate"]["image"] == app_image
        print(f"✓ compose config resolved image to {app_image}")
        
        # 3b. Verify docker compose create with --pull never succeeds
        docker(
            "compose",
            "-p", project_name,
            "-f", str(workspace / "docker-compose.yml"),
            "-f", str(workspace / "override.yml"),
            "create",
            "--pull", "never",
            "--no-build",
            "app",
            check=True,
        )
        print("✓ compose create --pull never succeeded")
        
        # Inspect running app container
        app_container_name = f"{project_name}-app-1"
        inspect_result = docker(
            "inspect",
            "--format", "{{.Image}}",
            app_container_name,
            check=True,
        )
        running_image = inspect_result.stdout.strip()
        assert running_image == app_image
        print(f"✓ app container image is {running_image}")
        
        # Verify no new images were created
        images_after = set(docker("images", "-q").stdout.strip().split("\n"))
        images_after.discard("")
        images_after.discard(app_image.replace("sha256:", ""))  # Remove our built image
        new_images = images_after - images_before
        assert not new_images, f"Unexpected new images created: {new_images}"
        print("✓ No new images created (probe image not counted)")
        
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
            "-f", str(workspace / "override.yml"),
            "create",
            "--pull", "never",
            "--no-build",
            "app",
            check=False,
        )
        assert fail_result.returncode != 0, "Expected create to fail with non-existent image"
        print("✓ compose create correctly failed with non-existent image")
        
    finally:
        # Cleanup: docker compose down
        docker(
            "compose",
            "-p", project_name,
            "-f", str(workspace / "docker-compose.yml"),
            "-f", str(workspace / "override.yml"),
            "down",
            "--volumes",
            "--remove-orphans",
            check=False,
        )
        # Remove throwaway image
        docker("image", "rm", app_image, check=False)
        print("✓ Cleanup complete")
