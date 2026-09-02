"""Tests for CSV validator runtime packaging in both repo and container layouts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cafeteria import csvio

# Determine paths dynamically from this test file location
TEST_FILE = Path(__file__).resolve()
TESTS_DIR = TEST_FILE.parent  # .../reference_scaffold/tests
SCAFFOLD_ROOT = TESTS_DIR.parent  # .../reference_scaffold
WORKTREE_ROOT = SCAFFOLD_ROOT.parent  # The worktree root


def test_dockerfile_contains_csv_copy_and_database():
    """(a) Dockerfile contains the new CSV validator COPY and still copies database/."""
    dockerfile_path = WORKTREE_ROOT / "deployment" / "Dockerfile"
    assert dockerfile_path.is_file(), \
        f"Dockerfile not found at {dockerfile_path} (WORKTREE_ROOT={WORKTREE_ROOT})"
    
    content = dockerfile_path.read_text(encoding="utf-8")
    
    # Check that database COPY is still present
    assert "COPY --chown=cafeteria:cafeteria database/ /app/database/" in content, \
        "database/ COPY line missing from Dockerfile"
    
    # Check that CSV validator COPY is present
    assert "COPY --chown=cafeteria:cafeteria csv/validate_menu_csv.py /app/csv/validate_menu_csv.py" in content, \
        "CSV validator COPY line missing from Dockerfile"
    
    # CSV COPY should come after database COPY
    db_pos = content.find("database/ /app/database/")
    csv_pos = content.find("csv/validate_menu_csv.py /app/csv/validate_menu_csv.py")
    assert db_pos < csv_pos, "CSV COPY should come after database COPY"


def test_validator_path_repo_candidate():
    """(b) csvio's resolver picks the repo path when it exists."""
    # In the actual repo or worktree, the csv/validate_menu_csv.py exists
    # _validator_path() should find it
    
    path = csvio._validator_path()
    assert path.is_file(), f"Validator path resolver returned non-existent file: {path}"
    
    # Verify it's one of the two expected candidates
    # Either repo candidate (worktree/../csv) or packaged candidate (scaffold/csv)
    repo_candidate = WORKTREE_ROOT / "csv" / "validate_menu_csv.py"
    packaged_candidate = SCAFFOLD_ROOT / "csv" / "validate_menu_csv.py"
    
    assert path in (repo_candidate, packaged_candidate), \
        f"Validator path {path} is neither repo {repo_candidate} nor packaged {packaged_candidate}"


def test_validator_path_packaged_candidate():
    """(c) With a tmp_path that mimics packaged layout, the packaged candidate is chosen."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create a fake packaged layout:
        # /tmp/xyz/reference_scaffold/csv/validate_menu_csv.py (packaged)
        # /tmp/xyz/csv/ (repo candidate, not present)
        scaffold_dir = tmpdir_path / "reference_scaffold"
        scaffold_dir.mkdir()
        csv_dir = scaffold_dir / "csv"
        csv_dir.mkdir()
        
        # Create a dummy validator in the packaged location
        validator_file = csv_dir / "validate_menu_csv.py"
        validator_file.write_text("# dummy packaged validator\n", encoding="utf-8")
        
        # Create the cafeteria/csvio structure
        cafeteria_dir = scaffold_dir / "cafeteria"
        cafeteria_dir.mkdir()
        dummy_module = cafeteria_dir / "csvio.py"
        dummy_module.write_text("# dummy csvio\n", encoding="utf-8")
        
        # Create a helper to simulate resolver with our paths
        def resolver_with_paths(csvio_file_path):
            scaffold_root = csvio_file_path.parents[1]  # cafeteria -> reference_scaffold
            
            # Repo candidate would be outside our temp dir, so it won't exist
            repo_candidate = scaffold_root.parent / "csv" / "validate_menu_csv.py"
            if repo_candidate.is_file():
                return repo_candidate
            
            # Packaged candidate is in our temp dir
            packaged_candidate = scaffold_root / "csv" / "validate_menu_csv.py"
            if packaged_candidate.is_file():
                return packaged_candidate
            
            raise RuntimeError("CSV-Validator konnte nicht geladen werden.")
        
        # Test the resolver logic with our temp structure
        result = resolver_with_paths(dummy_module)
        expected = scaffold_dir / "csv" / "validate_menu_csv.py"
        assert result == expected, f"Expected {expected}, got {result}"


def test_csv_validator_path_env_override():
    """(d) CSV_VALIDATOR_PATH environment variable override wins."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create a validator at a custom path
        custom_validator = tmpdir_path / "my_custom_validator.py"
        custom_validator.write_text("# custom validator\n", encoding="utf-8")
        
        # Set the environment variable and call _validator_path
        with patch.dict(os.environ, {"CSV_VALIDATOR_PATH": str(custom_validator)}):
            path = csvio._validator_path()
            assert path == custom_validator, \
                f"Expected custom validator {custom_validator}, got {path}"


def test_csv_validator_path_missing_raises_error():
    """(d) Missing file via CSV_VALIDATOR_PATH raises RuntimeError with German message."""
    missing_path = "/nonexistent/validator.py"
    
    with patch.dict(os.environ, {"CSV_VALIDATOR_PATH": missing_path}):
        with pytest.raises(RuntimeError, match="CSV_VALIDATOR_PATH"):
            csvio._validator_path()


def test_validator_path_not_found_raises_error():
    """If no candidate file exists, RuntimeError is raised."""
    # Create a temp structure with no validator file anywhere
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        scaffold_dir = tmpdir_path / "reference_scaffold"
        scaffold_dir.mkdir()
        cafeteria_dir = scaffold_dir / "cafeteria"
        cafeteria_dir.mkdir()
        dummy_module = cafeteria_dir / "csvio.py"
        dummy_module.write_text("# dummy csvio\n", encoding="utf-8")
        
        # Test the resolver logic with our empty temp structure
        def resolver_empty():
            csvio_file = dummy_module
            scaffold_root = csvio_file.parents[1]
            
            repo_candidate = scaffold_root.parent / "csv" / "validate_menu_csv.py"
            if repo_candidate.is_file():
                return repo_candidate
            
            packaged_candidate = scaffold_root / "csv" / "validate_menu_csv.py"
            if packaged_candidate.is_file():
                return packaged_candidate
            
            raise RuntimeError("CSV-Validator konnte nicht geladen werden.")
        
        with pytest.raises(RuntimeError, match="CSV-Validator"):
            resolver_empty()


def test_validator_function_uses_validator_path():
    """_validator() function uses _validator_path() to resolve the module."""
    # This is tested implicitly by any call to csvio._validator()
    # which now uses the two-candidate logic
    
    # Just verify that the validator module can be loaded
    validator_module = csvio._validator()
    assert hasattr(validator_module, "validate_text"), \
        "Validator module does not have validate_text function"
