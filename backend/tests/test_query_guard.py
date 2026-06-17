"""
tests/test_query_guard.py — Unit tests for the SQL injection / DML guard.

Tests verify that:
  - Valid SELECT queries pass through.
  - All DML (INSERT, UPDATE, DELETE) is rejected.
  - All DDL (DROP, CREATE, ALTER) is rejected.
  - Dangerous patterns (xp_cmdshell, EXEC, etc.) are rejected.
  - Comment stripping works correctly.
  - LIMIT injection works correctly.
  - Multiple statement injection is rejected.
"""

import pytest

from security.query_guard import QueryGuardError, guard, inject_limit, strip_comments


class TestStripComments:
    def test_strips_single_line_comment(self):
        sql = "SELECT * FROM sales -- drop table users"
        result = strip_comments(sql)
        assert "--" not in result
        assert "drop table" not in result.lower()

    def test_strips_block_comment(self):
        sql = "SELECT /* malicious comment */ * FROM sales"
        result = strip_comments(sql)
        assert "/*" not in result

    def test_preserves_query_body(self):
        sql = "SELECT id, revenue FROM sales WHERE region = 'North'"
        result = strip_comments(sql)
        assert "SELECT" in result.upper()
        assert "revenue" in result


class TestSelectOnly:
    def test_valid_select_passes(self):
        sql = "SELECT id, revenue FROM sales WHERE region = 'North' LIMIT 100"
        result = guard(sql)
        assert result is not None
        assert "SELECT" in result.upper()

    def test_select_with_group_by_passes(self):
        sql = "SELECT region, SUM(revenue) FROM sales GROUP BY region"
        result = guard(sql)
        assert "SELECT" in result.upper()

    def test_insert_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("INSERT INTO sales (region) VALUES ('Test')")

    def test_update_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("UPDATE sales SET revenue = 0")

    def test_delete_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("DELETE FROM sales WHERE id = 1")

    def test_drop_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("DROP TABLE sales")

    def test_create_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("CREATE TABLE evil (id INTEGER)")

    def test_alter_rejected(self):
        with pytest.raises(QueryGuardError, match="not allowed"):
            guard("ALTER TABLE sales ADD COLUMN evil TEXT")

    def test_truncate_rejected(self):
        with pytest.raises(QueryGuardError):
            guard("TRUNCATE TABLE sales")


class TestDangerousPatterns:
    def test_xp_cmdshell_rejected(self):
        with pytest.raises(QueryGuardError, match="Dangerous"):
            guard("SELECT xp_cmdshell('whoami')")

    def test_exec_rejected(self):
        with pytest.raises(QueryGuardError, match="Dangerous"):
            guard("SELECT * FROM sales; EXEC sp_executesql('DROP TABLE sales')")

    def test_load_file_rejected(self):
        with pytest.raises(QueryGuardError, match="Dangerous"):
            guard("SELECT load_file('/etc/passwd')")

    def test_into_outfile_rejected(self):
        with pytest.raises(QueryGuardError, match="Dangerous"):
            guard("SELECT * FROM sales INTO OUTFILE '/tmp/data.txt'")

    def test_pg_sleep_rejected(self):
        with pytest.raises(QueryGuardError, match="Dangerous"):
            guard("SELECT pg_sleep(10)")


class TestMultipleStatements:
    def test_multiple_statements_rejected(self):
        with pytest.raises(QueryGuardError, match="Multiple statements"):
            guard("SELECT * FROM sales; DROP TABLE sales")

    def test_single_statement_passes(self):
        result = guard("SELECT * FROM sales LIMIT 10")
        assert result is not None


class TestLimitInjection:
    def test_injects_limit_when_missing(self):
        sql = "SELECT * FROM sales"
        result = inject_limit(sql, max_rows=500)
        assert "LIMIT 500" in result.upper()

    def test_caps_existing_high_limit(self):
        sql = "SELECT * FROM sales LIMIT 999999"
        result = inject_limit(sql, max_rows=1000)
        assert "999999" not in result
        assert "LIMIT 1000" in result.upper()

    def test_does_not_double_inject_limit(self):
        sql = "SELECT * FROM sales LIMIT 50"
        result = inject_limit(sql, max_rows=1000)
        assert result.upper().count("LIMIT") == 1

    def test_strips_semicolon_before_limit(self):
        sql = "SELECT * FROM sales;"
        result = inject_limit(sql, max_rows=100)
        assert result.upper().count("LIMIT") == 1
        assert ";" not in result


class TestEmptyQuery:
    def test_empty_string_rejected(self):
        with pytest.raises(QueryGuardError):
            guard("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(QueryGuardError):
            guard("   ")
