import pytest

from app.repo.validators import validate_github_url, InvalidRepoUrlError


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/facebook/react", "https://github.com/facebook/react"),
        ("https://github.com/facebook/react/", "https://github.com/facebook/react"),
        ("https://github.com/facebook/react.git", "https://github.com/facebook/react"),
        ("  https://github.com/facebook/react  ", "https://github.com/facebook/react"),
    ],
)
def test_valid_urls_normalize_correctly(url, expected):
    assert validate_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/facebook/react",           # wrong host
        "https://github.com.evil.com/facebook/react",  # lookalike host
        "http://github.com/facebook/react",             # not https
        "https://github.com/facebook",                  # missing repo segment
        "https://github.com/facebook/react/extra",       # too many segments
        "https://github.com/",                           # no segments
        "not-a-url-at-all",                               # garbage input
        "https://github.com/face book/react",            # invalid characters
    ],
)
def test_invalid_urls_raise(url):
    with pytest.raises(InvalidRepoUrlError):
        validate_github_url(url)