import json
import tempfile
import unittest
from pathlib import Path

from reverie.backend_server.event_ledger import EventLedger
from reverie.backend_server.runtime_storage import RunStorage


class RunStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.storage = RunStorage(self.root)

        self.base_dir = (
            self.root
            / "environment"
            / "frontend_server"
            / "storage"
            / "base"
            / "demo_world"
        )
        (self.base_dir / "reverie").mkdir(parents=True)
        (self.base_dir / "environment").mkdir()
        (self.base_dir / "personas").mkdir()
        (self.base_dir / "reverie" / "meta.json").write_text(
            json.dumps(
                {
                    "fork_sim_code": "base_demo_world",
                    "start_date": "June 15, 2026",
                    "curr_time": "June 15, 2026, 09:00:00",
                    "sec_per_step": 10,
                    "maze_name": "the_ville",
                    "persona_names": ["Ada Lovelace"],
                    "step": 0,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_fork_accepts_legacy_base_prefix(self):
        resolved = self.storage.resolve_fork_path("base_demo_world")

        self.assertEqual(resolved, self.base_dir)

    def test_create_run_from_fork_updates_meta_and_current_pointers(self):
        run_dir = self.storage.create_run_from_fork("base_demo_world", "run_one")

        meta = self.storage.read_run_meta("run_one")
        pointer = self.storage.read_current_run_pointer()

        self.assertEqual(run_dir, self.storage.runs_dir / "run_one")
        self.assertEqual(meta["fork_sim_code"], "demo_world")
        self.assertEqual(pointer["sim_code"], "run_one")
        self.assertEqual(pointer["step"], 0)
        self.assertTrue((run_dir / "movement").is_dir())

    def test_write_json_keeps_previous_file_when_new_value_cannot_serialize(self):
        path = self.storage.temp_dir / "curr_step.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"step": 1}), encoding="utf-8")

        with self.assertRaises(TypeError):
            self.storage._write_json(path, {"step": object()})

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"step": 1})


class EventLedgerTests(unittest.TestCase):
    def test_append_event_records_auditable_jsonl_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EventLedger(Path(tmp) / "events.jsonl")

            event = ledger.append(
                "tool_request",
                actor="Tool Advocate",
                step=12,
                sim_time="June 15, 2026, 09:02:00",
                payload={"request_id": "req_1"},
            )

            entries = ledger.read_all()
            self.assertEqual(entries, [event])
            self.assertEqual(event["type"], "tool_request")
            self.assertEqual(event["actor"], "Tool Advocate")
            self.assertEqual(event["payload"]["request_id"], "req_1")
            self.assertIn("id", event)
            self.assertIn("created_at", event)


if __name__ == "__main__":
    unittest.main()
