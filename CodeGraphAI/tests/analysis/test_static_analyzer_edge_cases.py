"""
Edge case tests for Static Code Analyzer
"""

import unittest
from app.analysis.static_analyzer import StaticCodeAnalyzer


class TestStaticAnalyzerEdgeCases(unittest.TestCase):
    """Test edge cases in static analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = StaticCodeAnalyzer()

    def test_multi_line_comments(self):
        """Test handling of multi-line comments"""
        code = """
/*
 * This is a multi-line comment
 * It contains keywords like SELECT and UPDATE
 * But they should be ignored
 */
CREATE PROCEDURE test_proc AS
BEGIN
    SELECT * FROM real_table;  -- This is real
END;
"""
        result = self.analyzer.analyze_code(code, "test_proc")

        # Should find real_table, not anything in comments
        self.assertIn("real_table", [t.upper() for t in result.tables])

    def test_strings_with_sql_keywords(self):
        """Test strings containing SQL keywords"""
        code = """
CREATE PROCEDURE test_proc AS
    v_sql VARCHAR2(1000) := 'SELECT * FROM users WHERE name = ''DELETE''';
BEGIN
    EXECUTE IMMEDIATE v_sql;
    INSERT INTO log_table (message) VALUES ('UPDATE was successful');
END;
"""
        result = self.analyzer.analyze_code(code, "test_proc")

        # Should find log_table, not treat strings as actual SQL
        self.assertIn("log_table", [t.upper() for t in result.tables])

    def test_nested_procedures(self):
        """Test nested procedure definitions"""
        code = """
CREATE OR REPLACE PROCEDURE outer_proc AS
    PROCEDURE inner_proc IS
    BEGIN
        SELECT * FROM inner_table;
    END;
BEGIN
    SELECT * FROM outer_table;
    inner_proc();
END;
"""
        result = self.analyzer.analyze_code(code, "outer_proc")

        # Should find both inner_proc call and both tables
        self.assertGreater(len(result.procedures), 0)
        self.assertGreater(len(result.tables), 0)

    def test_dynamic_sql(self):
        """Test dynamic SQL detection"""
        code = """
CREATE PROCEDURE dynamic_proc(p_table_name VARCHAR2) AS
    v_sql VARCHAR2(4000);
BEGIN
    v_sql := 'SELECT * FROM ' || p_table_name;
    EXECUTE IMMEDIATE v_sql;

    -- Also has static SQL
    SELECT * FROM static_table;
END;
"""
        result = self.analyzer.analyze_code(code, "dynamic_proc")

        # Should find static_table
        # May or may not detect dynamic table (implementation dependent)
        self.assertIn("static_table", [t.upper() for t in result.tables])

    def test_complex_query_with_subqueries(self):
        """Test complex queries with multiple nested subqueries"""
        code = """
CREATE PROCEDURE complex_query AS
BEGIN
    SELECT a.*, b.name
    FROM (
        SELECT id FROM table1
        WHERE EXISTS (
            SELECT 1 FROM table2
            WHERE table2.id = table1.id
            AND status IN (
                SELECT status FROM table3
            )
        )
    ) a
    JOIN table4 b ON a.id = b.id;
END;
"""
        result = self.analyzer.analyze_code(code, "complex_query")

        # Should find all tables: table1, table2, table3, table4
        tables_upper = [t.upper() for t in result.tables]
        self.assertIn("TABLE1", tables_upper)
        self.assertIn("TABLE2", tables_upper)
        self.assertIn("TABLE3", tables_upper)
        self.assertIn("TABLE4", tables_upper)

    def test_case_insensitive_keywords(self):
        """Test case-insensitive keyword matching"""
        code = """
CREATE PROCEDURE mixed_case AS
BEGIN
    Select * From users;
    UPDATE Users SET name = 'test';
    delete from LOGS;
END;
"""
        result = self.analyzer.analyze_code(code, "mixed_case")

        # Should find all tables regardless of case
        tables_upper = [t.upper() for t in result.tables]
        self.assertIn("USERS", tables_upper)
        self.assertIn("LOGS", tables_upper)

    def test_procedure_calls_with_schema(self):
        """Test procedure calls with schema qualification"""
        code = """
CREATE PROCEDURE test_proc AS
BEGIN
    CALL schema1.proc1();
    EXECUTE schema2.proc2();
    schema3.proc3();
END;
"""
        result = self.analyzer.analyze_code(code, "test_proc")

        # Should find procedures with schema
        procs_upper = [p.upper() for p in result.procedures]
        self.assertTrue(any("PROC1" in p for p in procs_upper))
        self.assertTrue(any("PROC2" in p for p in procs_upper))
        self.assertTrue(any("PROC3" in p for p in procs_upper))

    def test_table_aliases(self):
        """Test extraction with table aliases"""
        code = """
CREATE PROCEDURE with_aliases AS
BEGIN
    SELECT u.name, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE u.status = 'active';
END;
"""
        result = self.analyzer.analyze_code(code, "with_aliases")

        # Should find actual table names, not aliases
        tables_upper = [t.upper() for t in result.tables]
        self.assertIn("USERS", tables_upper)
        self.assertIn("ORDERS", tables_upper)
        # Should NOT find 'u' or 'o' as tables
        self.assertNotIn("U", tables_upper)
        self.assertNotIn("O", tables_upper)

    def test_cte_common_table_expressions(self):
        """Test Common Table Expressions (WITH clause)"""
        code = """
CREATE PROCEDURE with_cte AS
BEGIN
    WITH user_orders AS (
        SELECT user_id, COUNT(*) as order_count
        FROM orders
        GROUP BY user_id
    ),
    active_users AS (
        SELECT * FROM users WHERE status = 'active'
    )
    SELECT u.name, uo.order_count
    FROM active_users u
    JOIN user_orders uo ON u.id = uo.user_id;
END;
"""
        result = self.analyzer.analyze_code(code, "with_cte")

        # Should find base tables: orders, users
        # CTEs (user_orders, active_users) are not base tables
        tables_upper = [t.upper() for t in result.tables]
        self.assertIn("ORDERS", tables_upper)
        self.assertIn("USERS", tables_upper)

    def test_exception_handling_blocks(self):
        """Test code with exception handling"""
        code = """
CREATE PROCEDURE with_exceptions AS
BEGIN
    BEGIN
        INSERT INTO main_table VALUES (1, 'test');
    EXCEPTION
        WHEN OTHERS THEN
            INSERT INTO error_log VALUES ('Error occurred');
            RAISE;
    END;
END;
"""
        result = self.analyzer.analyze_code(code, "with_exceptions")

        # Should find both tables
        tables_upper = [t.upper() for t in result.tables]
        self.assertIn("MAIN_TABLE", tables_upper)
        self.assertIn("ERROR_LOG", tables_upper)

    def test_procedure_with_packages(self):
        """Test procedure calls from packages"""
        code = """
CREATE PROCEDURE test_proc AS
BEGIN
    dbms_output.put_line('Test');
    my_package.my_procedure();
    SELECT * FROM my_package.my_table;
END;
"""
        result = self.analyzer.analyze_code(code, "test_proc")

        # Should find package procedures
        procs_upper = [p.upper() for p in result.procedures]
        self.assertTrue(any("MY_PROCEDURE" in p for p in procs_upper))

    def test_empty_procedure(self):
        """Test empty procedure"""
        code = """
CREATE PROCEDURE empty_proc AS
BEGIN
    NULL;
END;
"""
        result = self.analyzer.analyze_code(code, "empty_proc")

        # Should not crash, just return empty results
        self.assertEqual(len(result.tables), 0)
        self.assertEqual(len(result.procedures), 0)

    def test_procedure_with_only_comments(self):
        """Test procedure with only comments"""
        code = """
CREATE PROCEDURE comment_only AS
BEGIN
    -- This procedure does nothing
    /* Just comments */
END;
"""
        result = self.analyzer.analyze_code(code, "comment_only")

        # Should not crash
        self.assertIsNotNone(result)


class TestStaticAnalyzerParameterExtraction(unittest.TestCase):
    """Test parameter extraction edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = StaticCodeAnalyzer()

    def test_complex_parameter_types(self):
        """Test extraction of complex parameter types"""
        code = """
CREATE OR REPLACE PROCEDURE complex_params(
            p_in_param IN VARCHAR2,
    p_out_param OUT NUMBER,
    p_inout_param IN OUT DATE,
    p_default IN VARCHAR2 := 'default_value',
    p_table_type IN table_type_name,
    p_record_type IN record_type%ROWTYPE
) AS
BEGIN
    NULL;
END;
"""
        result = self.analyzer.analyze_code(code, "complex_params")

        # Should extract all parameters
        self.assertGreater(len(result.parameters), 0)

    def test_no_parameters(self):
        """Test procedure with no parameters"""
        code = """
CREATE PROCEDURE no_params AS
BEGIN
    SELECT * FROM users;
END;
"""
        result = self.analyzer.analyze_code(code, "no_params")

        # Should have empty parameter list
        self.assertEqual(len(result.parameters), 0)


if __name__ == '__main__':
    unittest.main()

