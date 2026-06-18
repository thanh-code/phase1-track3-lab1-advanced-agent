from src.reflexion_lab.agents import LATSAgent, ReActAgent, ReflexionAgent
from src.reflexion_lab.mock_runtime import MockRuntime
from src.reflexion_lab.schemas import LATSConfig
from src.reflexion_lab.utils import load_dataset


def test_mock_react_reflexion_and_lats_flow():
    examples = load_dataset("data/hotpot_mini.json")
    hp2 = next(example for example in examples if example.qid == "hp2")
    runtime = MockRuntime()

    react = ReActAgent(runtime=runtime).run(hp2)
    assert react.agent_type == "react"
    assert react.is_correct is False

    reflexion = ReflexionAgent(runtime=runtime, max_attempts=3).run(hp2)
    assert reflexion.agent_type == "reflexion"
    assert reflexion.is_correct is True
    assert reflexion.attempts > 1
    assert len(reflexion.reflections) >= 1

    lats = LATSAgent(runtime=runtime, config=LATSConfig()).run(hp2)
    assert lats.agent_type == "lats"
    assert lats.is_correct is True
    assert 1 <= len(lats.lats_trace) <= 5
    assert lats.token_estimate > 0
