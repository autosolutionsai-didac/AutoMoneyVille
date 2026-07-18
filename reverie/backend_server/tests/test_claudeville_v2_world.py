import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "reverie" / "backend_server"
ASSETS = ROOT / "environment" / "frontend_server" / "static_dirs" / "assets"
BASES = ROOT / "environment" / "frontend_server" / "storage" / "base"
SPEC_PATH = ROOT / "tools" / "mapgen" / "town_spec.json"
V1_DIGEST = "c3b26ccb87a4d609d9b42623f4fa77773b2ea041d124abc47997fa500a9f8272"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import maze as maze_module  # noqa: E402
from address_aliases import AddressTileIndex, load_address_aliases  # noqa: E402
from path_finder import PathFinder  # noqa: E402

from tools.mapgen import generate_world  # noqa: E402

CANONICAL_SECTORS = {
    "Bank",
    "University",
    "Agent Academy",
    "Post Office",
    "Market",
    "Workshop",
    "Community Center",
    "Library",
    "Town Hall",
    "Central Plaza",
    "Claudeville Cafe",
    *(f"Home {number}" for number in range(1, 11)),
}
LEGACY_SECTORS = {
    "Banco",
    "Universidad",
    "Academia de Agentes",
    "Oficina de Correos",
    "Mercado",
    "Taller de Trabajo",
    "Sala de Acuerdos",
    "Biblioteca",
    "Oficina de Gobierno",
    *(f"Residencia {number}" for number in range(1, 11)),
}
PUBLIC_DESTINATIONS = (
    "Bank",
    "University",
    "Agent Academy",
    "Market",
    "Post Office",
    "Workshop",
    "Community Center",
    "Library",
    "Town Hall",
    "Central Plaza",
    "Claudeville Cafe",
)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _spatial_memory_from_spec(spec: dict) -> dict:
    world = spec["world_name"]
    memory = {world: {}}
    for sector in spec["sectors"]:
        memory[world].setdefault(sector["name"], {})
    for arena in spec["arenas"]:
        memory[world].setdefault(arena["sector"], {}).setdefault(arena["name"], [])
    for obj in spec["objects"]:
        objects = memory[world][obj["sector"]].setdefault(obj["arena"], [])
        if obj["type"] not in objects:
            objects.append(obj["type"])
    return memory


class ClaudevilleV2WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        maze_module.maze_assets_loc = str(ASSETS)
        cls.maze = maze_module.Maze("claudeville")
        cls.spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    def test_spec_has_english_non_overlapping_sectors_and_central_semantics(self):
        grid = self.spec["grid"]
        self.assertEqual(
            (grid["maze_width"], grid["maze_height"], grid["sq_tile_size"]),
            (88, 48, 32),
        )
        sector_names = {sector["name"] for sector in self.spec["sectors"]}
        self.assertEqual(sector_names, CANONICAL_SECTORS)
        self.assertTrue(LEGACY_SECTORS.isdisjoint(sector_names))

        occupied = {}
        for sector in self.spec["sectors"]:
            x0, y0, x1, y1 = sector["rect"]
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    self.assertNotIn((x, y), occupied)
                    occupied[(x, y)] = sector["name"]

        objects = {
            (entry["sector"], entry["arena"], entry["type"])
            for entry in self.spec["objects"]
        }
        self.assertTrue(
            {
                ("Central Plaza", "plaza", "fountain"),
                ("Central Plaza", "plaza", "bench"),
                ("Central Plaza", "plaza", "notice board"),
                ("Claudeville Cafe", "cafe.service", "service counter"),
                ("Claudeville Cafe", "cafe.dining", "dining table"),
                ("Claudeville Cafe", "cafe.terrace", "terrace table"),
            }.issubset(objects)
        )

    def test_canonical_and_legacy_addresses_resolve_but_output_is_english(self):
        cases = {
            "Claudeville:Banco:main:counter": (
                "Claudeville:Bank:bank.teller:teller counter"
            ),
            "Claudeville:Academia de Agentes:classroom:classroom student seating": (
                "Claudeville:Agent Academy:academy.classroom:classroom seating"
            ),
            "Claudeville:Biblioteca:reading room:library table": (
                "Claudeville:Library:library.reading:reading table"
            ),
            "Claudeville:Residencia 2:bedroom:bed": (
                "Claudeville:Home 2:home_2.main_room"
            ),
        }
        for legacy, canonical in cases.items():
            with self.subTest(legacy=legacy):
                self.assertEqual(self.maze.resolve_address(legacy), canonical)
                self.assertEqual(
                    self.maze.address_tiles[legacy],
                    self.maze.address_tiles[canonical],
                )
                self.assertNotIn(legacy, self.maze.address_tiles.keys())

        legacy, canonical = next(iter(cases.items()))
        tile = next(iter(self.maze.address_tiles[legacy]))
        self.assertEqual(self.maze.get_tile_path(tile, "game_object"), canonical)

    def test_required_claudeville_alias_manifest_fails_closed_when_missing(self):
        meta_path = ASSETS / "claudeville" / "matrix" / "maze_meta_info.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(
            meta["address_alias_manifest"], "legacy_address_aliases.v1.json"
        )

        rejected = False
        with tempfile.TemporaryDirectory() as tmp:
            try:
                load_address_aliases(Path(tmp) / "missing.v1.json", required=True)
            except FileNotFoundError:
                rejected = True
            except TypeError:
                pass
        self.assertTrue(rejected, "a declared alias manifest must fail closed")

        with tempfile.TemporaryDirectory() as tmp:
            isolated_assets = Path(tmp) / "assets"
            shutil.copytree(
                ASSETS / "claudeville" / "matrix",
                isolated_assets / "claudeville" / "matrix",
            )
            original_assets = maze_module.maze_assets_loc
            try:
                maze_module.maze_assets_loc = str(isolated_assets)
                with self.assertRaises(FileNotFoundError):
                    maze_module.Maze("claudeville")
            finally:
                maze_module.maze_assets_loc = original_assets

    def test_alias_targets_must_exist_in_canonical_address_index(self):
        index = AddressTileIndex({})
        index["Claudeville:Bank"] = {(1, 1)}
        rejected = False
        try:
            index.set_aliases({"Banco": "Claudeville:Missing"})
        except ValueError:
            rejected = True
        except AttributeError:
            pass
        self.assertTrue(rejected, "unknown canonical alias targets must be rejected")

        manifest = load_address_aliases(
            ASSETS / "claudeville" / "legacy_address_aliases.v1.json"
        )
        self.assertTrue(set(manifest.values()).issubset(self.maze.address_tiles.keys()))

    def test_collision_fallback_uses_non_claudeville_world_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collision = (
                root
                / "environment/frontend_server/static_dirs/assets/testopolis"
                / "matrix/maze/collision_maze.csv"
            )
            collision.parent.mkdir(parents=True)
            collision.write_text("0, 777, 777, 0", encoding="utf-8")

            grid = generate_world.load_collision_source(
                world="Testopolis",
                width=2,
                height=2,
                collision_block_id="777",
                repo_root=root,
                draft_path=root / "missing-draft.json",
            )

        self.assertEqual(grid, [[False, True], [True, False]])

    def test_world_asset_root_rejects_traversal_before_collision_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            escaped_collision = (
                root
                / "environment/frontend_server/static_dirs/matrix/maze"
                / "collision_maze.csv"
            )
            escaped_collision.parent.mkdir(parents=True)
            escaped_collision.write_text("0, 777, 777, 0", encoding="utf-8")

            invalid_names = (
                ".",
                "..",
                "../escape",
                "..\\escape",
                "nested/world",
                "nested\\world",
            )
            for world in invalid_names:
                with self.subTest(world=world), self.assertRaises(ValueError):
                    generate_world.load_collision_source(
                        world=world,
                        width=2,
                        height=2,
                        collision_block_id="777",
                        repo_root=root,
                        draft_path=root / "missing-draft.json",
                    )

            world_root = generate_world.resolve_world_asset_root(
                "Testopolis", repo_root=root
            )
            assets_root = (
                root / "environment/frontend_server/static_dirs/assets"
            ).resolve()
            self.assertEqual(world_root.parent, assets_root)

    def test_required_destinations_are_reachable_by_canonical_address(self):
        required = {f"Claudeville:{name}" for name in CANONICAL_SECTORS}
        required.update(
            {
                "Claudeville:Central Plaza:plaza:fountain",
                "Claudeville:Central Plaza:plaza:bench",
                "Claudeville:Central Plaza:plaza:notice board",
                "Claudeville:Claudeville Cafe:cafe.service:service counter",
                "Claudeville:Claudeville Cafe:cafe.dining:dining table",
                "Claudeville:Claudeville Cafe:cafe.terrace:terrace table",
            }
        )
        for address in required:
            with self.subTest(address=address):
                self.assertTrue(self.maze.address_tiles.get(address))

    def test_v2_has_ten_walkable_spawns_and_only_english_world_references(self):
        base = BASES / "claudeville_v2"
        meta = json.loads((base / "reverie" / "meta.json").read_text(encoding="utf-8"))
        environment = json.loads(
            (base / "environment" / "0.json").read_text(encoding="utf-8")
        )
        self.assertEqual(meta["fork_sim_code"], "base_claudeville_v2")
        self.assertEqual(meta["persona_names"], list(environment))
        self.assertEqual(len(environment), 10)
        for spawn in environment.values():
            self.assertEqual(spawn["maze"], "claudeville")
            self.assertEqual(self.maze.collision_maze[spawn["y"]][spawn["x"]], "0")

        for name in meta["persona_names"]:
            boot = base / "personas" / name / "bootstrap_memory"
            scratch = json.loads((boot / "scratch.json").read_text(encoding="utf-8"))
            spatial = json.loads(
                (boot / "spatial_memory.json").read_text(encoding="utf-8")
            )
            self.assertEqual(set(spatial["Claudeville"]), CANONICAL_SECTORS)
            self.assertEqual(
                spatial,
                _spatial_memory_from_spec(self.spec),
                "active spatial memory must mirror the current semantic map",
            )
            self.assertEqual(
                scratch.get("living_area"),
                "Claudeville:Home 1:home_1.bedroom",
            )
            self.assertIn(
                "Agent Academy:academy.classroom",
                scratch.get("daily_plan_req", ""),
            )
            references = json.dumps(
                {
                    "living_area": scratch.get("living_area"),
                    "daily_plan_req": scratch.get("daily_plan_req"),
                    "daily_req": scratch.get("daily_req"),
                    "schedule": scratch.get("f_daily_schedule"),
                    "hourly": scratch.get("f_daily_schedule_hourly_org"),
                    "act_address": scratch.get("act_address"),
                },
                ensure_ascii=False,
            )
            for legacy in LEGACY_SECTORS:
                self.assertNotIn(legacy, references)

    def test_every_v2_resident_can_path_to_every_public_destination(self):
        base = BASES / "claudeville_v2"
        environment = json.loads(
            (base / "environment" / "0.json").read_text(encoding="utf-8")
        )
        finder = PathFinder(self.maze.collision_maze, self.maze.collision_block_id)

        def reachable_from(start):
            reachable = {start}
            pending = [start]
            while pending:
                x, y = pending.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    candidate = (x + dx, y + dy)
                    cx, cy = candidate
                    if (
                        candidate not in reachable
                        and 0 <= cx < self.maze.maze_width
                        and 0 <= cy < self.maze.maze_height
                        and self.maze.collision_maze[cy][cx] == "0"
                    ):
                        reachable.add(candidate)
                        pending.append(candidate)
            return reachable

        self.assertEqual(len(environment), 10)
        for resident, spawn in environment.items():
            start = (spawn["x"], spawn["y"])
            reachable = reachable_from(start)
            for sector in PUBLIC_DESTINATIONS:
                address = f"Claudeville:{sector}"
                targets = sorted(
                    reachable.intersection(self.maze.address_tiles[address])
                )
                with self.subTest(resident=resident, destination=sector):
                    self.assertTrue(targets, f"no reachable floor tile in {address}")
                    path = finder.find_path(start, targets[0])
                    self.assertEqual(path[0], start)
                    self.assertEqual(path[-1], targets[0])
                    self.assertFalse(finder.last_path_truncated)

    def test_all_active_v2_json_and_world_matrices_use_english_facility_names(self):
        active_files = list((BASES / "claudeville_v2").rglob("*.json"))
        active_files.append(SPEC_PATH)
        active_files.extend(
            path
            for path in (ASSETS / "claudeville" / "matrix").rglob("*")
            if path.is_file()
        )
        self.assertTrue(active_files)
        for path in active_files:
            content = path.read_text(encoding="utf-8")
            for legacy in LEGACY_SECTORS:
                with self.subTest(path=path.relative_to(ROOT), legacy=legacy):
                    self.assertNotIn(legacy, content)

    def test_claudeville_v1_archive_is_byte_for_byte_unchanged(self):
        self.assertEqual(_tree_digest(BASES / "claudeville_v1"), V1_DIGEST)

    def test_task_owned_changed_files_are_strictly_under_500_lines(self):
        files = [
            ASSETS / "claudeville" / "legacy_address_aliases.v1.json",
            ROOT / "reverie" / "backend_server" / "address_aliases.py",
            ROOT / "reverie" / "backend_server" / "maze.py",
            Path(__file__),
            ROOT / "tools" / "mapgen" / "generate_world.py",
            ROOT / "tools" / "mapgen" / "make_claudeville_base.py",
            SPEC_PATH,
        ]
        for tree in (
            ASSETS / "claudeville" / "matrix",
            BASES / "claudeville_v2",
        ):
            files.extend(path for path in tree.rglob("*") if path.is_file())

        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(line_count, 500)


if __name__ == "__main__":
    unittest.main()
