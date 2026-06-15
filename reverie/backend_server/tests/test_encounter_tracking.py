import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.reverie import ReverieServer
from persona.persona import Persona


class MazeStub:
    def has_line_of_sight(self, _tile_a, _tile_b):
        return True


class ScratchStub:
    def __init__(self, chatting_with=None, vision_r=8):
        self.chatting_with = chatting_with
        self.vision_r = vision_r


class ConversationScratchStub:
    chatting_with = "Nora Vale"
    chat = [["Nora Vale", "Can we coordinate?"]]
    conversation_group_id = "group-1"

    def get_conversation_participants(self):
        return ["Nora Vale", "Theo Grant"]


class EncounterTrackingTests(unittest.TestCase):
    def test_detect_new_encounters_accepts_three_part_nearby_records(self):
        server = SimpleNamespace(
            personas={
                "Nora Vale": SimpleNamespace(
                    scratch=ScratchStub(),
                    _acknowledged_nearby={("Theo Grant", ("is", "working"), 8)},
                ),
                "Theo Grant": SimpleNamespace(
                    scratch=ScratchStub(),
                    _acknowledged_nearby={("Nora Vale", ("is", "working"), 8)},
                ),
            },
            personas_tile={"Nora Vale": (16, 19), "Theo Grant": (19, 27)},
            maze=MazeStub(),
        )

        encounters = ReverieServer._detect_new_encounters(server)

        self.assertEqual(encounters, [])

    def test_get_nearby_conversations_accepts_three_part_nearby_records(self):
        persona = Persona.__new__(Persona)
        persona.name = "Milo Chen"
        persona._acknowledged_nearby = {
            ("Nora Vale", ("is", "planning"), 3),
            ("Theo Grant", ("is", "drafting"), 4),
        }
        personas = {
            "Nora Vale": SimpleNamespace(scratch=ConversationScratchStub()),
            "Theo Grant": SimpleNamespace(scratch=ScratchStub()),
        }

        conversations = Persona._get_nearby_conversations(persona, personas)

        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["participants"], ["Nora Vale", "Theo Grant"])


if __name__ == "__main__":
    unittest.main()
