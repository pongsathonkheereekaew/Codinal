import pytest

from validation import validate_user


def test_valid_user():
    validate_user({"name": "alice", "email": "alice@example.com"})


def test_missing_name():
    with pytest.raises(ValueError):
        validate_user({"email": "alice@example.com"})
