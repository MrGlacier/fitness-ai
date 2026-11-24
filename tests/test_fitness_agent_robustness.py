import unittest
from types import SimpleNamespace

from fitness.fitness_agent import FitnessAgent


class FakeLlmClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.questions = []

    def ask(self, question, **kwargs):
        self.questions.append(question)
        return {"success": True, "answer": self.answers.pop(0)}


class FakeMcpClient:
    def __init__(self, tool_answer=None):
        self.tool_answer = tool_answer

    async def list_tools(self):
        tool = SimpleNamespace(
            name="hello",
            inputSchema={"type": "object"},
            description="Begrüßt eine Person.",
        )
        return SimpleNamespace(tools=[tool])

    async def call_tool(self, tool_name, arguments):
        return self.tool_answer


class FitnessAgentRobustnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_tool_plan_with_missing_fields(self):
        agent = FitnessAgent(
            llm_client_instance=FakeLlmClient(['{"status":"found"}']),
            mcp_client_instance=FakeMcpClient(),
        )

        with self.assertRaisesRegex(ValueError, "gültigen Tool-Plan"):
            await agent.ask("Hallo")

    async def test_rejects_found_tool_plan_without_tools(self):
        agent = FitnessAgent(
            llm_client_instance=FakeLlmClient([
                '{"status":"found","response_type":"data","tools":[]}'
            ]),
            mcp_client_instance=FakeMcpClient(),
        )

        with self.assertRaisesRegex(ValueError, "keine Tools"):
            await agent.ask("Hallo")

    async def test_uses_plain_text_mcp_result_without_json_error(self):
        tool_answer = SimpleNamespace(
            structuredContent=None,
            content=[SimpleNamespace(text="Hallo Ada!")],
        )
        llm_client = FakeLlmClient([
            """{
                "status": "found",
                "response_type": "data",
                "tools": [{
                    "tool": "hello",
                    "arguments": {"name": "Ada"},
                    "description": "Begrüßung"
                }]
            }""",
            "Hallo Ada!",
        ])
        agent = FitnessAgent(
            llm_client_instance=llm_client,
            mcp_client_instance=FakeMcpClient(tool_answer),
        )

        result = await agent.ask("Begrüße Ada")

        self.assertEqual(result, "Hallo Ada!")
        self.assertIn("Hallo Ada!", llm_client.questions[1])


if __name__ == "__main__":
    unittest.main()


class LocalPlanContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_plan_is_in_planning_and_answer_even_when_other_tool_is_used(self):
        context = dict(status="available", name="Example Build", week=6,
                       sessions=[dict(title="Original Test Session", duration_sec=3600)])
        llm = FakeLlmClient([
            '{"status":"found","response_type":"data","tools":[{"tool":"hello","arguments":{}}]}',
            'Dein zugeordneter Plan ist Example Build, Woche 6.',
        ])
        agent = FitnessAgent(llm, FakeMcpClient(), plan_context_provider=lambda: context)
        answer = await agent.ask("Welchen Trainingsplan trainiere ich?")
        assert "Woche 6" in answer
        assert "Example Build" in llm.questions[0]
        assert "Original Test Session" in llm.questions[1]

    async def test_local_plan_can_be_answered_when_planner_finds_no_external_tool(self):
        llm = FakeLlmClient(['{"status":"failed","response_type":"data","tools":[]}', 'Woche 6'])
        agent = FitnessAgent(llm, FakeMcpClient(), plan_context_provider=lambda: dict(status="available", week=6))
        assert await agent.ask("Welche Planwoche ist aktuell?") == "Woche 6"
