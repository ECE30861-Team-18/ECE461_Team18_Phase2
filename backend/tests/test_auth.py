# import pytest

# # Adjust this import path if needed depending on your structure
# from app.auth import validate_token, require_auth


# # -------- validate_token() TESTS -------- #

# def test_validate_token_success():
#     headers = {"X-Authorization": "bearer aaa.bbb.ccc"}
#     assert validate_token(headers) is True


# def test_validate_token_missing_header():
#     headers = {}
#     assert validate_token(headers) is False


# def test_validate_token_empty_value():
#     headers = {"X-Authorization": ""}
#     assert validate_token(headers) is False


# def test_validate_token_wrong_prefix():
#     headers = {"X-Authorization": "token aaa.bbb.ccc"}
#     assert validate_token(headers) is False


# def test_validate_token_not_jwt_format():
#     headers = {"X-Authorization": "bearer invalid_token"}
#     assert validate_token(headers) is False


# # -------- require_auth() TESTS -------- #

# def test_require_auth_success():
#     event = {"headers": {"X-Authorization": "bearer x.y.z"}}
#     valid, error = require_auth(event)
#     assert valid is True
#     assert error is None


# def test_require_auth_failure_missing():
#     event = {"headers": {}}
#     valid, error = require_auth(event)
#     assert valid is False
#     assert error["statusCode"] == 403


# def test_require_auth_failure_bad_format():
#     event = {"headers": {"X-Authorization": "bearer not_a_jwt"}}
#     valid, error = require_auth(event)
#     assert valid is False
#     assert error["statusCode"] == 403
