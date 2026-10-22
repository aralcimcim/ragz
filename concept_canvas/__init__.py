from pathlib import Path

import streamlit.components.v1 as components


_canvas = components.declare_component("research_canvas", path=str(Path(__file__).with_name("frontend")))


def research_canvas(catalog, state, evidence, matching_count, initial_state, ack):
    return _canvas(catalog=catalog, state=state, evidence=evidence, matching_count=matching_count,
                   initial_state=initial_state, ack=ack, default=None, key="research_canvas")
