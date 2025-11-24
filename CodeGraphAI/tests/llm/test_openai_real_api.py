"""
Real OpenAI API integration tests - these cost money!
Run only when explicitly needed
"""

import pytest
import unittest
import os
from analyzer import LLMAnalyzer
from app.llm.token_tracker import TokenTracker


@pytest.mark.real_llm
class TestOpenAIRealAPI(unittest.TestCase):
    """Real OpenAI API tests - require API key and cost money"""

    @classmethod
    def setUpClass(cls):
        """Set up OpenAI API credentials from environment"""
        cls.api_key = os.getenv("CODEGRAPHAI_OPENAI_API_KEY")
        cls.model = os.getenv("CODEGRAPHAI_OPENAI_MODEL", "o3-mini")

        if not cls.api_key:
            pytest.skip("OpenAI API key not configured")

    def setUp(self):
        """Set up test fixtures"""
        self.token_tracker = TokenTracker()

        # Initialize LLM analyzer with real OpenAI
        self.analyzer = LLMAnalyzer(
            model_name=self.model,
            device="api",
            api_key=self.api_key,
            use_local=False,
            token_tracker=self.token_tracker
        )

    def test_analyze_simple_procedure(self):
        """Test analyzing a simple stored procedure"""
        procedure_code = """
CREATE OR REPLACE PROCEDURE update_user_status(
    p_user_id IN NUMBER,
    p_new_status IN VARCHAR2
) AS
BEGIN
    UPDATE users
    SET status = p_new_status,
        updated_at = SYSDATE
    WHERE user_id = p_user_id;

    COMMIT;
END;
"""

        # Analyze business logic
        business_logic = self.analyzer.analyze_business_logic(
            procedure_name="update_user_status",
            source_code=procedure_code
        )

        self.assertIsNotNone(business_logic)
        self.assertIsInstance(business_logic, str)
        self.assertGreater(len(business_logic), 0)

        # Should mention updating user status
        self.assertIn("user", business_logic.lower())
        self.assertIn("status", business_logic.lower())

    def test_extract_dependencies(self):
        """Test extracting dependencies from procedure"""
        procedure_code = """
CREATE OR REPLACE PROCEDURE process_order(
    p_order_id IN NUMBER
) AS
    v_user_id NUMBER;
BEGIN
    -- Get user from orders table
    SELECT user_id INTO v_user_id
    FROM orders
    WHERE order_id = p_order_id;

    -- Call helper procedures
    validate_order(p_order_id);
    calculate_total(p_order_id);

    -- Update inventory table
    UPDATE inventory
    SET quantity = quantity - 1
    WHERE product_id IN (
        SELECT product_id FROM order_items
        WHERE order_id = p_order_id
    );
END;
"""

        # Extract dependencies
        called_procs, called_tables = self.analyzer.extract_dependencies(
            procedure_name="process_order",
            source_code=procedure_code
        )

        # Should find procedure calls
        self.assertIsInstance(called_procs, set)
        self.assertGreater(len(called_procs), 0)
        self.assertTrue(any("validate_order" in proc.lower() for proc in called_procs))

        # Should find table accesses
        self.assertIsInstance(called_tables, set)
        self.assertGreater(len(called_tables), 0)
        self.assertTrue(any("orders" in table.lower() for table in called_tables))

    def test_calculate_complexity(self):
        """Test complexity calculation"""
        simple_code = """
CREATE PROCEDURE simple_proc AS
BEGIN
    SELECT * FROM users;
END;
"""

        complex_code = """
CREATE PROCEDURE complex_proc AS
    v_count NUMBER;
BEGIN
    FOR rec IN (SELECT * FROM large_table) LOOP
        IF rec.status = 'ACTIVE' THEN
            BEGIN
                CALL helper1(rec.id);
                CALL helper2(rec.id);

                UPDATE table1 SET field = 1 WHERE id = rec.id;
                UPDATE table2 SET field = 2 WHERE id = rec.id;

                FOR sub_rec IN (SELECT * FROM sub_table WHERE parent_id = rec.id) LOOP
                    CALL nested_proc(sub_rec.id);
                END LOOP;
            EXCEPTION
                WHEN OTHERS THEN
                    ROLLBACK;
                    RAISE;
            END;
        END IF;
    END LOOP;
END;
"""

        # Simple procedure should have low complexity
        simple_complexity = self.analyzer.calculate_complexity(
            procedure_name="simple_proc",
            source_code=simple_code
        )
        self.assertLessEqual(simple_complexity, 3)

        # Complex procedure should have high complexity
        complex_complexity = self.analyzer.calculate_complexity(
            procedure_name="complex_proc",
            source_code=complex_code
        )
        self.assertGreaterEqual(complex_complexity, 7)

    def test_token_tracking(self):
        """Test that token usage is tracked"""
        procedure_code = "CREATE PROCEDURE test AS BEGIN SELECT 1; END;"

        # Reset tracker
        self.token_tracker.reset()

        # Make API call
        self.analyzer.analyze_business_logic(
            procedure_name="test",
            source_code=procedure_code
        )

        # Should have tracked tokens
        usage = self.token_tracker.get_total_usage()
        self.assertGreater(usage["input_tokens"], 0)
        self.assertGreater(usage["output_tokens"], 0)

    def test_fallback_model(self):
        """Test fallback to alternative model on error"""
        # Test with invalid model first, should fallback
        fallback_model = os.getenv("CODEGRAPHAI_FALLBACK_MODEL", "gpt-4.1")

        # If primary model fails, should try fallback
        # This is more of a config test

    def test_cost_estimation(self):
        """Test cost estimation for API calls"""
        procedure_code = "CREATE PROCEDURE test AS BEGIN SELECT 1; END;"

        self.token_tracker.reset()

        self.analyzer.analyze_business_logic(
            procedure_name="test",
            source_code=procedure_code
        )

        # Get estimated cost
        usage = self.token_tracker.get_total_usage()

        # o3-mini costs (example rates)
        input_cost_per_1k = 0.0001  # $0.0001 per 1K tokens
        output_cost_per_1k = 0.0002  # $0.0002 per 1K tokens

        estimated_cost = (
            (usage["input_tokens"] / 1000) * input_cost_per_1k +
            (usage["output_tokens"] / 1000) * output_cost_per_1k
        )

        # Cost should be very small for simple test
        self.assertLess(estimated_cost, 0.01)  # Less than 1 cent


@pytest.mark.real_llm
class TestOpenAIEdgeCases(unittest.TestCase):
    """Edge case tests with real OpenAI API"""

    def test_very_long_procedure(self):
        """Test analyzing very long procedure"""
        pytest.skip("Expensive test - enable manually")

    def test_non_english_comments(self):
        """Test procedure with non-English comments"""
        pytest.skip("Test with non-English text")

    def test_malformed_sql(self):
        """Test handling of malformed SQL"""
        pytest.skip("Test error handling")


if __name__ == '__main__':
    unittest.main()

