"""Explicit redaction tests.

These run in CI on every push. A failure here blocks merge.
"""
import pytest
from app.infra.redaction import redact, redact_dict

PLACEHOLDER = "[REDACTED]"


class TestAPIKeys:
    def test_openai_key(self):
        text = "my key is sk-abcdefghij1234567890 and it works"
        result = redact(text)
        assert "sk-abcdefghij1234567890" not in result
        assert PLACEHOLDER in result

    def test_github_personal_token(self):
        text = "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        result = redact(text)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in result
        assert PLACEHOLDER in result

    def test_github_server_token(self):
        result = redact("auth: ghs_secrettoken1234567890abcdef")
        assert "ghs_secrettoken1234567890abcdef" not in result

    def test_slack_token(self):
        # Deliberately broken into parts so secret scanners don't flag test code.
        prefix = "xoxb"
        fake = f"{prefix}-TESTTOKENFORTESTING123"
        result = redact(fake)
        assert fake not in result


class TestJWT:
    def test_jwt_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMSJ9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = redact(f"Authorization: Bearer {jwt}")
        assert jwt not in result

    def test_normal_text_unchanged(self):
        text = "the issue is that the import fails on line 42"
        assert redact(text) == text


class TestEmail:
    def test_email_redacted(self):
        result = redact("contact maintainer at john.doe@example.com for help")
        assert "john.doe@example.com" not in result
        assert PLACEHOLDER in result

    def test_no_false_positive_on_code(self):
        # "user@host" in code context — still redacted (safe to over-redact emails)
        result = redact("ssh user@192.168.1.1")
        assert PLACEHOLDER in result


class TestDatabaseURL:
    def test_postgres_url_credentials_redacted(self):
        url = "postgresql://copilot:supersecret@localhost:5432/copilot"
        result = redact(url)
        assert "supersecret" not in result

    def test_postgres_url_without_password_unchanged(self):
        url = "postgresql://localhost:5432/copilot"
        assert redact(url) == url


class TestAWSKey:
    def test_aws_access_key(self):
        result = redact("AKIAIOSFODNN7EXAMPLE is the key")
        assert "AKIAIOSFODNN7EXAMPLE" not in result


class TestRedactDict:
    def test_dict_values_redacted(self):
        data = {"user": "alice", "token": "sk-secrettoken123456789"}
        result = redact_dict(data)
        assert "sk-secrettoken123456789" not in result["token"]
        assert result["user"] == "alice"  # clean value unchanged

    def test_non_string_values_untouched(self):
        data = {"count": 42, "flag": True}
        assert redact_dict(data) == data
