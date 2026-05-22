import pytest
from src.tts import VoicePool

def test_assigns_voice_to_new_character():
    pool = VoicePool(voices=["VoiceA", "VoiceB", "VoiceC"])
    v = pool.get_voice("Alice")
    assert v == "VoiceA"

def test_same_character_gets_same_voice():
    pool = VoicePool(voices=["VoiceA", "VoiceB"])
    v1 = pool.get_voice("Alice")
    v2 = pool.get_voice("Alice")
    assert v1 == v2

def test_different_characters_get_different_voices():
    pool = VoicePool(voices=["VoiceA", "VoiceB", "VoiceC"])
    v1 = pool.get_voice("Alice")
    v2 = pool.get_voice("Bob")
    assert v1 != v2

def test_narrator_uses_fixed_voice():
    pool = VoicePool(voices=["VoiceA", "VoiceB"], narrator_voice="NarratorVoice")
    v = pool.get_voice("Narrator")
    assert v == "NarratorVoice"

def test_wraps_around_when_pool_exhausted():
    pool = VoicePool(voices=["VoiceA", "VoiceB"])
    pool.get_voice("Alice")
    pool.get_voice("Bob")
    v = pool.get_voice("Carol")
    assert v == "VoiceA"

def test_load_existing_assignments():
    pool = VoicePool(voices=["VoiceA", "VoiceB"], existing={"Alice": "VoiceB"})
    assert pool.get_voice("Alice") == "VoiceB"

def test_get_all_assignments():
    pool = VoicePool(voices=["VoiceA", "VoiceB"])
    pool.get_voice("Alice")
    pool.get_voice("Bob")
    assignments = pool.assignments()
    assert assignments == {"Alice": "VoiceA", "Bob": "VoiceB"}
