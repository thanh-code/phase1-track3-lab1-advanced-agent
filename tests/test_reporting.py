from src.reflexion_lab.agents import LATSAgent, ReActAgent, ReflexionAgent
from src.reflexion_lab.mock_runtime import MockRuntime
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.schemas import LATSConfig
from src.reflexion_lab.utils import load_dataset


def test_report_contains_benchmark_tables(tmp_path):
    examples = load_dataset("data/hotpot_mini.json")[:2]
    runtime = MockRuntime()
    records = []
    for example in examples:
        records.append(ReActAgent(runtime=runtime).run(example))
        records.append(ReflexionAgent(runtime=runtime).run(example))
        records.append(LATSAgent(runtime=runtime, config=LATSConfig()).run(example))

    report = build_report(records, dataset_name="hotpot_mini.json", mode="mock", golden=True)
    assert "react" in report.summary
    assert "reflexion" in report.summary
    assert "lats" in report.summary
    assert report.react_vs_reflexion_table
    assert report.cost_runtime_table
    assert report.golden_submission is not None

    json_path, md_path = save_report(report, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert (tmp_path / "visual_report.html").exists()
    assert (tmp_path / "analysis" / "react_vs_reflexion_table.json").exists()
    assert (tmp_path / "analysis" / "cost_runtime_table.json").exists()
    assert (tmp_path / "analysis" / "golden_submission.json").exists()
