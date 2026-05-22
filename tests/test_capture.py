import pytest
from src.capture import parse_dialogue, has_changed, CaptureState

def test_parse_character_and_dialogue():
    name, text = parse_dialogue("Alice\nHello, how are you?")
    assert name == "Alice"
    assert text == "Hello, how are you?"

def test_parse_multiline_dialogue():
    name, text = parse_dialogue("Bob\nThis is line one.\nThis is line two.")
    assert name == "Bob"
    assert text == "This is line one. This is line two."

def test_parse_narration_no_name():
    name, text = parse_dialogue("The sun rose slowly over the hills.")
    assert name == "Narrator"
    assert text == "The sun rose slowly over the hills."

def test_parse_strips_whitespace():
    name, text = parse_dialogue("  Maria  \n  That's part of my job.  ")
    assert name == "Maria"
    assert text == "That's part of my job."

def test_parse_empty_string():
    name, text = parse_dialogue("")
    assert name == ""
    assert text == ""

def test_has_changed_detects_new_text():
    state = CaptureState()
    assert has_changed("Hello world", state) is True

def test_has_changed_same_text_returns_false():
    state = CaptureState()
    has_changed("Hello world", state)
    assert has_changed("Hello world", state) is False

def test_has_changed_different_text_returns_true():
    state = CaptureState()
    has_changed("Hello world", state)
    assert has_changed("Goodbye world", state) is True
