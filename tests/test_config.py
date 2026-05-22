import json
import os
import pytest
from src.config import Config

def test_defaults_when_no_file(tmp_path):
    cfg = Config(path=str(tmp_path / "config.json"))
    assert cfg.region is None
    assert cfg.voices == {}
    assert cfg.speed == 1.0

def test_save_and_load(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = Config(path=path)
    cfg.region = {"top": 100, "left": 200, "width": 800, "height": 150}
    cfg.voices["Alice"] = "en-US-JennyNeural"
    cfg.speed = 1.5
    cfg.save()

    cfg2 = Config(path=path)
    assert cfg2.region == {"top": 100, "left": 200, "width": 800, "height": 150}
    assert cfg2.voices["Alice"] == "en-US-JennyNeural"
    assert cfg2.speed == 1.5

def test_save_creates_file(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = Config(path=path)
    cfg.save()
    assert os.path.exists(path)

def test_assign_voice_persists(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = Config(path=path)
    cfg.set_voice("Bob", "en-GB-RyanNeural")
    cfg.save()
    cfg2 = Config(path=path)
    assert cfg2.voices["Bob"] == "en-GB-RyanNeural"
