"""
Tests for CodeAnalysisAgent - LangChain agent for intelligent code analysis
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from app.agents.code_analysis_agent import CodeAnalysisAgent


class TestCodeAnalysisAgentInitialization(unittest.TestCase):
    """Test agent initialization"""

    def test_agent_initialization_with_minimal_params(self):
        """Test agent initialization with minimal parameters"""
        mock_llm = Mock()
        mock_tools = [Mock()]

        agent = CodeAnalysisAgent(
            llm=mock_llm,
            tools=mock_tools
        )

        self.assertIsNotNone(agent)
        self.assertEqual(agent.llm, mock_llm)
        self.assertEqual(agent.tools, mock_tools)
        self.assertEqual(agent.max_iterations, 15)
        self.assertEqual(agent.max_execution_time, 300)
        self.assertFalse(agent.verbose)

    def test_agent_initialization_with_custom_params(self):
        """Test agent initialization with custom parameters"""
        mock_llm = Mock()
        mock_tools = [Mock(), Mock()]

        agent = CodeAnalysisAgent(
            llm=mock_llm,
            tools=mock_tools,
            verbose=True,
            max_iterations=10,
            max_execution_time=600
        )

        self.assertEqual(agent.max_iterations, 10)
        self.assertEqual(agent.max_execution_time, 600)
        self.assertTrue(agent.verbose)

    @patch('app.agents.code_analysis_agent.create_agent')
    def test_agent_initialization_creates_agent_graph(self, mock_create_agent):
        """Test that agent initialization creates agent graph"""
        mock_llm = Mock()
        mock_tools = [Mock()]
        mock_graph = Mock()
        mock_create_agent.return_value = mock_graph

        agent = CodeAnalysisAgent(
            llm=mock_llm,
            tools=mock_tools
        )

        mock_create_agent.assert_called_once()
        self.assertIsNotNone(agent.agent_graph)

    @patch('app.agents.code_analysis_agent.create_agent')
    def test_agent_initialization_failure(self, mock_create_agent):
        """Test agent initialization failure handling"""
        mock_llm = Mock()
        mock_tools = [Mock()]
        mock_create_agent.side_effect = Exception("Failed to create agent")

        with self.assertRaises(Exception):
            CodeAnalysisAgent(llm=mock_llm, tools=mock_tools)


class TestCodeAnalysisAgentAnalyze(unittest.TestCase):
    """Test agent analyze functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.mock_tools = [Mock()]

        with patch('app.agents.code_analysis_agent.create_agent'):
            self.agent = CodeAnalysisAgent(
                llm=self.mock_llm,
                tools=self.mock_tools
            )

    def test_analyze_simple_query(self):
        """Test simple query analysis"""
        # Setup mock agent graph
        mock_message = Mock()
        mock_message.content = "This is the answer"
        mock_message.tool_calls = []

        self.agent.agent_graph = Mock()
        self.agent.agent_graph.invoke.return_value = {
            "messages": [mock_message]
        }

        # Execute
        result = self.agent.analyze("What does procedure X do?")

        # Verify
        self.assertTrue(result["success"])
        self.assertIn("answer", result)
        self.assertIn("This is the answer", result["answer"])

    def test_analyze_query_with_tool_calls(self):
        """Test query that triggers tool calls"""
        # Setup mock with tool calls
        mock_tool_call = Mock()
        mock_tool_call.name = "query_procedure"
        mock_tool_call.args = {"procedure_name": "TEST_PROC"}
        mock_tool_call.id = "call_123"

        mock_message = Mock()
        mock_message.content = "Found procedure info"
        mock_message.tool_calls = [mock_tool_call]

        self.agent.agent_graph = Mock()
        self.agent.agent_graph.invoke.return_value = {
            "messages": [mock_message]
        }

        # Execute
        result = self.agent.analyze("Tell me about procedure TEST_PROC")

        # Verify
        self.assertTrue(result["success"])
        self.assertGreater(result["tool_call_count"], 0)
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["tool"], "query_procedure")

    def test_analyze_without_initialization(self):
        """Test analyze fails if agent not initialized"""
        self.agent.agent_graph = None

        result = self.agent.analyze("Test query")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_analyze_exception_handling(self):
        """Test analyze handles exceptions gracefully"""
        self.agent.agent_graph = Mock()
        self.agent.agent_graph.invoke.side_effect = Exception("Agent error")

        result = self.agent.analyze("Test query")

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Agent error", result["error"])

    def test_analyze_complex_query_multiple_iterations(self):
        """Test complex query that requires multiple tool calls"""
        # Setup mock with multiple messages
        mock_msg1 = Mock()
        mock_msg1.content = "Let me check..."
        mock_msg1.tool_calls = []

        mock_msg2 = Mock()
        mock_msg2.content = "Found the information"
        mock_msg2.tool_calls = []

        self.agent.agent_graph = Mock()
        self.agent.agent_graph.invoke.return_value = {
            "messages": [mock_msg1, mock_msg2]
        }

        result = self.agent.analyze("Complex question about procedures")

        self.assertTrue(result["success"])
        self.assertIn("answer", result)


class TestCodeAnalysisAgentBatch(unittest.TestCase):
    """Test batch analysis functionality"""

    def setUp(self):
        """Set up test fixtures"""
        with patch('app.agents.code_analysis_agent.create_agent'):
            self.agent = CodeAnalysisAgent(
                llm=Mock(),
                tools=[Mock()]
            )

        # Setup mock agent graph
        mock_message = Mock()
        mock_message.content = "Answer"
        mock_message.tool_calls = []

        self.agent.agent_graph = Mock()
        self.agent.agent_graph.invoke.return_value = {
            "messages": [mock_message]
        }

    def test_batch_analyze_multiple_queries(self):
        """Test batch analysis of multiple queries"""
        queries = [
            "What does procedure A do?",
            "Show me table B structure",
            "Trace field C"
        ]

        results = self.agent.batch_analyze(queries)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result["success"])
            self.assertIn("answer", result)

    def test_batch_analyze_empty_list(self):
        """Test batch analysis with empty list"""
        results = self.agent.batch_analyze([])

        self.assertEqual(len(results), 0)

    def test_batch_analyze_single_query(self):
        """Test batch analysis with single query"""
        results = self.agent.batch_analyze(["Single query"])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])


@pytest.mark.real_llm
class TestCodeAnalysisAgentRealLLM:
    """Real LLM integration tests - these cost money and require API keys"""

    def test_real_openai_simple_query(self):
        """Test with real OpenAI API (requires API key)"""
        pytest.skip("Real LLM test - enable manually with API key")

    def test_real_anthropic_simple_query(self):
        """Test with real Anthropic API (requires API key)"""
        pytest.skip("Real LLM test - enable manually with API key")


if __name__ == '__main__':
    unittest.main()

