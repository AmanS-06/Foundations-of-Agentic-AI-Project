"""The Streamlit app runs headlessly (Streamlit AppTest): every scenario renders every view."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app.py")
VIEWS = ["Overview", "Conversation", "Decision", "Critic", "Trace", "Documents", "System"]


def run_scenario(prefix: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120).run()
    choice = next(o for o in at.selectbox[0].options if o.startswith(prefix))
    at.selectbox[0].select(choice).run()
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("prefix, verdict", [("S1", "Approved after 2"), ("S3", "Escalated")])
def test_scenario_renders_every_view(prefix, verdict):
    at = run_scenario(prefix)
    assert any(verdict in m.value for m in at.markdown)
    for view in VIEWS:
        at.segmented_control[0].set_value(view).run()
        assert not at.exception, (view, at.exception)
