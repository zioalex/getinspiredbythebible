#!/usr/bin/env python3
"""
Validate environment variable consistency between docker-compose and Terraform.

This script ensures that environment variables defined in the manifest are
properly configured in both local (docker-compose) and remote (Terraform)
deployment configurations.

Usage:
    python scripts/validate-env.py [--verbose]
"""

import argparse
import re
import sys
from pathlib import Path

import yaml


def parse_docker_compose_env_vars(compose_file: Path) -> dict[str, set[str]]:
    """Extract environment variables from docker-compose.yml."""
    with open(compose_file) as f:
        compose = yaml.safe_load(f)

    env_vars: dict[str, set[str]] = {}
    services = compose.get("services", {})

    for service_name, service_config in services.items():
        env_list = service_config.get("environment", [])
        service_vars: set[str] = set()

        for env_item in env_list:
            if isinstance(env_item, str):
                # Format: "VAR=${VAR:-default}" or "VAR=value"
                var_name = env_item.split("=")[0].strip()
                service_vars.add(var_name)
            elif isinstance(env_item, dict):
                # Format: {VAR: value}
                service_vars.update(env_item.keys())

        env_vars[service_name] = service_vars

    return env_vars


def parse_terraform_env_vars(tf_file: Path) -> dict[str, set[str]]:
    """Extract environment variables from Terraform main.tf.

    Handles two formats:
    1. Old format: individual env { name = "VAR" ... } blocks
    2. New format: locals map with "VAR" = { value = ... } entries
    """
    with open(tf_file) as f:
        content = f.read()

    env_vars: dict[str, set[str]] = {}

    # Parse locals block for env var maps (new format)
    # Look for backend_env_vars and frontend_env_vars in locals
    backend_vars_from_locals: set[str] = set()
    frontend_vars_from_locals: set[str] = set()

    # Find backend_env_vars map in locals
    backend_map_match = re.search(
        r'backend_env_vars\s*=\s*merge\s*\((.*?)\n  \)',
        content,
        re.DOTALL
    )
    if backend_map_match:
        map_content = backend_map_match.group(1)
        # Find all "VAR_NAME" = { entries
        var_pattern = r'"([A-Z][A-Z0-9_]*)"\s*=\s*\{'
        backend_vars_from_locals = set(re.findall(var_pattern, map_content))

    # Find frontend_env_vars map in locals
    frontend_map_match = re.search(
        r'frontend_env_vars\s*=\s*\{(.*?)\n  \}',
        content,
        re.DOTALL
    )
    if frontend_map_match:
        map_content = frontend_map_match.group(1)
        var_pattern = r'"([A-Z][A-Z0-9_]*)"\s*=\s*\{'
        frontend_vars_from_locals = set(re.findall(var_pattern, map_content))

    # Fall back to old format: find container app resources
    container_pattern = r'resource\s+"azurerm_container_app"\s+"(\w+)"\s*\{(.*?)^\}'
    matches = re.findall(container_pattern, content, re.MULTILINE | re.DOTALL)

    for resource_name, resource_body in matches:
        env_vars[resource_name] = set()

        # Check if using dynamic block with locals (new format)
        if "local.backend_env_vars" in resource_body:
            env_vars[resource_name] = backend_vars_from_locals
        elif "local.frontend_env_vars" in resource_body:
            env_vars[resource_name] = frontend_vars_from_locals
        else:
            # Old format: Find all env blocks with name = "VAR_NAME"
            env_pattern = r'name\s*=\s*"([A-Z][A-Z0-9_]*)"'
            env_block_pattern = r'(?:env|content)\s*\{([^}]+)\}'
            env_blocks = re.findall(env_block_pattern, resource_body)

            for block in env_blocks:
                name_match = re.search(env_pattern, block)
                if name_match:
                    var_name = name_match.group(1)
                    if not var_name.startswith("acr"):
                        env_vars[resource_name].add(var_name)

    return env_vars


def load_manifest(manifest_file: Path) -> dict:
    """Load the environment variable manifest."""
    with open(manifest_file) as f:
        return yaml.safe_load(f)


def validate(
    manifest: dict,
    compose_vars: dict[str, set[str]],
    terraform_vars: dict[str, set[str]],
    verbose: bool = False,
) -> tuple[list[str], list[str]]:
    """Validate environment variables against manifest."""
    errors: list[str] = []
    warnings: list[str] = []

    # Flatten compose vars (api + frontend services)
    local_backend_vars = compose_vars.get("api", set())
    local_frontend_vars = compose_vars.get("frontend", set())
    local_all_vars = local_backend_vars | local_frontend_vars

    # Flatten terraform vars
    remote_backend_vars = terraform_vars.get("backend", set())
    remote_frontend_vars = terraform_vars.get("frontend", set())
    remote_all_vars = remote_backend_vars | remote_frontend_vars

    if verbose:
        print("\n=== Docker Compose Variables ===")
        print(f"API service: {sorted(local_backend_vars)}")
        print(f"Frontend service: {sorted(local_frontend_vars)}")
        print("\n=== Terraform Variables ===")
        print(f"Backend: {sorted(remote_backend_vars)}")
        print(f"Frontend: {sorted(remote_frontend_vars)}")
        print()

    variables = manifest.get("variables", {})

    for var_name, var_config in variables.items():
        required_in = var_config.get("required_in", "both")
        condition = var_config.get("condition")
        is_frontend = var_name.startswith("NEXT_PUBLIC_") or var_name == "NODE_ENV"

        # Determine which sets to check
        if is_frontend:
            local_check = local_frontend_vars
            remote_check = remote_frontend_vars
        else:
            local_check = local_backend_vars
            remote_check = remote_backend_vars

        # Check local (docker-compose)
        if required_in in ("local", "both"):
            if var_name not in local_check:
                if condition:
                    warnings.append(
                        f"LOCAL: {var_name} not set (conditional: {condition})"
                    )
                else:
                    errors.append(f"LOCAL: {var_name} missing in docker-compose.yml")

        # Check remote (Terraform)
        if required_in in ("remote", "both"):
            if var_name not in remote_check:
                if condition:
                    warnings.append(
                        f"REMOTE: {var_name} not set (conditional: {condition})"
                    )
                else:
                    errors.append(f"REMOTE: {var_name} missing in Terraform main.tf")

    # Check for undocumented variables (in configs but not in manifest)
    manifest_vars = set(variables.keys())

    undocumented_local = local_all_vars - manifest_vars
    undocumented_remote = remote_all_vars - manifest_vars

    for var in undocumented_local:
        warnings.append(f"LOCAL: {var} in docker-compose but not in manifest")

    for var in undocumented_remote:
        warnings.append(f"REMOTE: {var} in Terraform but not in manifest")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate environment variable consistency"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    manifest_file = script_dir / "env-manifest.yaml"
    compose_file = project_root / "docker-compose.yml"
    terraform_file = project_root / "deployment" / "main.tf"

    # Check files exist
    for f in [manifest_file, compose_file, terraform_file]:
        if not f.exists():
            print(f"ERROR: File not found: {f}")
            sys.exit(1)

    # Parse files
    manifest = load_manifest(manifest_file)
    compose_vars = parse_docker_compose_env_vars(compose_file)
    terraform_vars = parse_terraform_env_vars(terraform_file)

    # Validate
    errors, warnings = validate(manifest, compose_vars, terraform_vars, args.verbose)

    # Report results
    if warnings:
        print("\n=== Warnings ===")
        for w in sorted(warnings):
            print(f"  - {w}")

    if errors:
        print("\n=== Errors ===")
        for e in sorted(errors):
            print(f"  - {e}")
        print(f"\n{len(errors)} error(s) found.")
        sys.exit(1)

    if args.strict and warnings:
        print(f"\n{len(warnings)} warning(s) found (strict mode).")
        sys.exit(1)

    print("\nEnvironment variable validation passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
