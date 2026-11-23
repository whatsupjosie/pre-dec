import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from editor_core.editor_router import route_editor_command


def test_routes_synonym_request_to_thesaurus():
    d = route_editor_command("Can you give me a synonym for 'tired'?")
    assert d.tool == "thesaurus"


def test_routes_rhyme_request_to_rhyme():
    d = route_editor_command("What rhymes with 'window'?")
    assert d.tool == "rhyme"


def test_routes_continuity_request():
    d = route_editor_command("Wait, is this consistent with what I already established?")
    assert d.tool == "continuity"


def test_unclear_message_returns_unclear():
    d = route_editor_command("Hello there, how's it going?")
    assert d.tool == "unclear"
    assert d.confidence == 0.0
