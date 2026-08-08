import pytest

from app.repo.git_service import clone_repository, cleanup_clone
from app.repo.metadata_service import extract_metadata


@pytest.mark.integration
def test_extract_metadata_from_real_repo():
    cloned = clone_repository("https://github.com/octocat/Hello-World")
    try:
        metadata = extract_metadata(cloned.path)

        assert metadata.readme_content is not None
        assert "Hello" in metadata.readme_content

        assert metadata.file_count > 0

        # Hello-World is a near-empty demo repo with no source files,
        # so primary_language may legitimately be None here.
    finally:
        cleanup_clone(cloned)


def test_extract_metadata_ignores_git_dir(tmp_path):
    # Build a small fake repo on disk instead of hitting the network,
    # so this test is fast and doesn't depend on GitHub being reachable.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("fake git internals")

    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.py").write_text("def helper(): pass")
    (tmp_path / "README.md").write_text("# My Project\n\nA test project.")

    metadata = extract_metadata(tmp_path)

    assert metadata.file_count == 3  # main.py, utils.py, README.md — NOT .git/config
    assert metadata.primary_language == "Python"
    assert "My Project" in metadata.readme_content


def test_extract_metadata_handles_missing_readme(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")

    metadata = extract_metadata(tmp_path)

    assert metadata.readme_content is None
    assert metadata.file_count == 1
    assert metadata.primary_language == "Python"