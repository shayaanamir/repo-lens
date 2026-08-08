import pytest

from app.repo.git_service import clone_repository, cleanup_clone, CloneError


@pytest.mark.integration
def test_clone_small_public_repo():
    cloned = clone_repository("https://github.com/octocat/Hello-World")
    try:
        assert cloned.path.exists()
        assert cloned.size_bytes > 0
        assert (cloned.path / "README").exists() or (cloned.path / "README.md").exists()
    finally:
        cleanup_clone(cloned)
        assert not cloned.path.exists()


@pytest.mark.integration
def test_clone_nonexistent_repo_raises():
    with pytest.raises(CloneError):
        clone_repository("https://github.com/this-owner-does-not-exist-xyz/nope")