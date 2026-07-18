import json
import subprocess
from pathlib import Path
from unittest import mock

from django.test import RequestFactory, SimpleTestCase
from PIL import Image

from translator import views

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = FRONTEND_ROOT / "static_dirs"
TEMPLATE_ROOT = FRONTEND_ROOT / "templates"
RENDERER = STATIC_ROOT / "js" / "world_renderer.js"
ADDRESSES = STATIC_ROOT / "js" / "world_addresses.js"
JS_HARNESS = Path(__file__).resolve().parent / "js_tests/world_renderer_harness.js"
CONTRACT_MANIFEST = STATIC_ROOT / "assets/claudeville/world.json"
ALIAS_MANIFEST = STATIC_ROOT / "assets/claudeville/legacy_address_aliases.v1.json"


def _manifest(world):
    path = STATIC_ROOT / "assets" / world / "world.json"
    if not path.is_file():
        raise AssertionError(f"missing frontend world manifest: {path}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _run_node(source):
    result = subprocess.run(
        ["node", "-e", source],
        cwd=FRONTEND_ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def _aliases():
    return json.loads(ALIAS_MANIFEST.read_text(encoding="utf-8"))["aliases"]


class WorldManifestTests(SimpleTestCase):
    maxDiff = None

    def test_world_manifests_are_safe_complete_frontend_contracts(self):
        expected = {
            "the_ville": (140, 100, "assets/the_ville/visuals/the_ville_jan7.json"),
            "claudeville": (88, 48, None),
        }
        for world, (width, height, tilemap_url) in expected.items():
            path, manifest = _manifest(world)
            self.assertEqual(manifest["version"], 2 if world == "claudeville" else 1)
            self.assertEqual(manifest["world"], world)
            self.assertEqual(
                manifest["dimensions"],
                {"width": width, "height": height, "tile_size": 32},
            )
            if tilemap_url:
                self.assertEqual(manifest["tilemap_url"], tilemap_url)
            else:
                self.assertTrue(manifest["tilemap_url"].startswith("assets/claudeville/"))
                self.assertTrue(manifest["tilemap_url"].endswith(".json"))
            self.assertTrue(manifest["layer_order"])
            self.assertEqual(
                manifest["character_manifest_url"], "assets/characters/atlas.json"
            )
            self.assertEqual(
                manifest["character_atlas_image_url"], "img/atlas.png"
            )
            self.assertEqual(
                manifest["resident_manifest_url"], "assets/characters/manifest.json"
            )
            self.assertTrue(manifest["legacy_background_fallback_url"])
            self.assertTrue(manifest["tilesets"])
            if world == "claudeville":
                self.assertNotIn("aliases", manifest)
                self.assertEqual(
                    manifest["address_alias_manifest_url"],
                    "assets/claudeville/legacy_address_aliases.v1.json",
                )
                self.assertEqual(
                    manifest["visual_dimensions"],
                    {"width": 176, "height": 96, "tile_size": 16},
                )
                self.assertNotIn("scene_image_url", manifest)
                self.assertEqual(manifest["facades"], [])
                self.assertEqual(
                    manifest["tile_layers"],
                    [
                        name for name in manifest["layer_order"]
                        if name not in {"Depth Props", "Overhead Props"}
                    ],
                )
                self.assertEqual(
                    [layer["name"] for layer in manifest["object_layers"]],
                    ["Depth Props", "Overhead Props"],
                )
                self.assertEqual(
                    [layer["depth_mode"] for layer in manifest["object_layers"]],
                    ["foot-y", "fixed"],
                )
                self.assertEqual(
                    [atlas["key"] for atlas in manifest["atlases"]],
                    ["claudeville-v2-props"],
                )
                self.assertEqual(manifest["rendering"], {"texture_filter": "nearest"})
                self.assertEqual(
                    manifest["depth_model"],
                    {"actor_base": 2000, "overhead_depth": 90000},
                )
                self.assertTrue(manifest["credits_url"].endswith("/runtime/credits.json"))
            else:
                self.assertIsInstance(manifest["aliases"], dict)

            tilemap_path = STATIC_ROOT / manifest["tilemap_url"]
            tilemap = json.loads(tilemap_path.read_text(encoding="utf-8"))
            map_layers = [layer["name"] for layer in tilemap["layers"]]
            if world == "claudeville":
                self.assertEqual(map_layers, manifest["layer_order"])
            else:
                self.assertEqual(
                    manifest["layer_order"],
                    [name for name in map_layers if name in manifest["layer_order"]],
                )
            visual = manifest.get("visual_dimensions", manifest["dimensions"])
            self.assertEqual(
                (tilemap["width"], tilemap["height"], tilemap["tilewidth"], tilemap["tileheight"]),
                (visual["width"], visual["height"], visual["tile_size"], visual["tile_size"]),
            )
            self.assertEqual(tilemap["width"] * tilemap["tilewidth"], width * 32)
            self.assertEqual(tilemap["height"] * tilemap["tileheight"], height * 32)

    def test_claudeville_manifest_uses_approved_aliases_and_legacy_png_as_fallback(self):
        _, manifest = _manifest("claudeville")
        self.assertNotIn("aliases", manifest)
        self.assertEqual(
            manifest["address_alias_manifest_url"],
            "assets/claudeville/legacy_address_aliases.v1.json",
        )
        self.assertTrue(_aliases())
        self.assertEqual(
            manifest["legacy_background_fallback_url"],
            "assets/claudeville/visuals/claudeville_bg.png",
        )
        self.assertNotEqual(
            manifest["tilemap_url"], manifest["legacy_background_fallback_url"]
        )

    def test_claudeville_manifest_urls_resolve_to_bounded_local_assets(self):
        _, manifest = _manifest("claudeville")
        urls = [
            manifest["tilemap_url"],
            manifest["address_alias_manifest_url"],
            manifest["character_manifest_url"],
            manifest["character_atlas_image_url"],
            manifest["resident_manifest_url"],
            manifest["legacy_background_fallback_url"],
            manifest["credits_url"],
            *(tileset["image_url"] for tileset in manifest["tilesets"]),
            *(facade["image_url"] for facade in manifest["facades"]),
            *(atlas[field] for atlas in manifest.get("atlases", []) for field in ("image_url", "data_url")),
        ]
        resident_manifest = json.loads(
            (STATIC_ROOT / manifest["resident_manifest_url"]).read_text(
                encoding="utf-8"
            )
        )
        urls.extend(
            url
            for resident in resident_manifest["residents"]
            for url in (resident["sprite_url"], resident["portrait_url"])
        )

        static_root = STATIC_ROOT.resolve()
        for url in urls:
            with self.subTest(url=url):
                relative = Path(url)
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                asset = (STATIC_ROOT / relative).resolve()
                self.assertIn(static_root, asset.parents)
                self.assertTrue(asset.is_file(), f"missing runtime asset: {url}")
                if asset.suffix.lower() == ".png":
                    with Image.open(asset) as image:
                        self.assertLessEqual(max(image.size), 4096)

        tilemap_path = (STATIC_ROOT / manifest["tilemap_url"]).resolve()
        tilemap = json.loads(tilemap_path.read_text(encoding="utf-8"))
        for tileset in tilemap["tilesets"]:
            image_path = (tilemap_path.parent / tileset["image"]).resolve()
            with self.subTest(tilemap_image=tileset["image"]):
                self.assertIn(static_root, image_path.parents)
                self.assertTrue(image_path.is_file())
                with Image.open(image_path) as image:
                    self.assertLessEqual(max(image.size), 4096)

    def test_view_context_selects_only_known_world_manifests(self):
        self.assertEqual(
            views._world_render_context({"maze_name": "claudeville"})[
                "world_manifest_path"
            ],
            "assets/claudeville/world.json",
        )
        unknown = views._world_render_context({"maze_name": "../../secrets"})
        self.assertEqual(unknown["maze_name"], "the_ville")
        self.assertEqual(unknown["world_manifest_path"], "assets/the_ville/world.json")


class WorldRendererTemplateTests(SimpleTestCase):
    def test_node_harness_covers_loader_failures_containment_and_scaled_fallback(self):
        result = subprocess.run(
            [
                "node",
                str(JS_HARNESS),
                str(RENDERER),
                str(CONTRACT_MANIFEST),
                str(STATIC_ROOT / "assets/the_ville/world.json"),
                str(ALIAS_MANIFEST),
            ],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_layer_creation_follows_manifest_order_and_falls_back_without_tilemap(self):
        renderer = json.dumps(str(RENDERER))
        manifest_path = json.dumps(str(CONTRACT_MANIFEST))
        node_source = """
            const renderer = require(__RENDERER__);
            const manifest = require(__MANIFEST__);
            const created = [];
            const layer = () => ({ setDepth() { return this; },
                setCollisionByProperty() { return this; } });
            const map = { width: 176, height: 96, tileWidth: 16, tileHeight: 16,
                widthInPixels: 2816, heightInPixels: 1536,
                layers: manifest.tile_layers.map(name => ({name})),
                objects: manifest.object_layers.map(value => ({name: value.name})),
                addTilesetImage(name, key) { return {name, key}; },
                createLayer(name) { created.push(name); return layer(); },
                getObjectLayer() { return {objects: []}; } };
            const sceneImage = {setOrigin() {return this;}, setDepth() {return this;}};
            const scene = { cache: {tilemap: {exists: () => true}},
                make: {tilemap: () => map}, add: {image() { return sceneImage; }} };
            const rendered = renderer.createWorld(scene, manifest);

            let fallbackKey = null;
            const fallbackScene = { cache: {tilemap: {exists: () => false}},
                textures: {exists: () => true},
                add: {image(x, y, key) { fallbackKey = key;
                    return {setOrigin() {return this;}, setDisplaySize() {return this;},
                        setDepth() {return this;}};
                }} };
            const fallback = renderer.createWorld(fallbackScene, manifest);
            console.log(JSON.stringify({created, bounds: rendered.bounds,
                usedFallback: fallback.usedFallback, fallbackKey}));
            """
        output = _run_node(
            node_source.replace("__RENDERER__", renderer).replace(
                "__MANIFEST__", manifest_path
            )
        )
        contract = json.loads(CONTRACT_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(output["created"], contract["tile_layers"])
        self.assertEqual(output["bounds"], {"width": 2816, "height": 1536})
        self.assertTrue(output["usedFallback"])
        self.assertEqual(output["fallbackKey"], "world-legacy-background")

    def test_alias_renderer_translates_known_fragments_without_mutating_input(self):
        addresses = json.dumps(str(ADDRESSES))
        aliases = json.dumps(_aliases())
        node_source = """
            const addresses = require(__ADDRESSES__);
            const aliases = __ALIASES__;
            const historical = 'walking @Claudeville:Oficina de Gobierno:main';
            addresses.setAliases(aliases);
            console.log(JSON.stringify({
                translated: addresses.translateText(historical),
                display: addresses.displayAddress('Claudeville:Banco:main:counter'),
                historical
            }));
            """
        output = _run_node(
            node_source.replace("__ADDRESSES__", addresses).replace(
                "__ALIASES__", aliases
            )
        )
        self.assertEqual(
            output["translated"],
            "walking @Claudeville:Town Hall:hall.public_service",
        )
        self.assertEqual(
            output["display"], "Bank \u203a bank.teller \u203a teller counter"
        )
        self.assertEqual(
            output["historical"], "walking @Claudeville:Oficina de Gobierno:main"
        )

    def test_historical_display_text_translates_and_then_escapes_in_real_js(self):
        addresses = json.dumps(str(ADDRESSES))
        aliases_path = json.dumps(str(ALIAS_MANIFEST))
        home_script = json.dumps(str(TEMPLATE_ROOT / "home/main_script.html"))
        node_source = r"""
            const fs = require('fs');
            const vm = require('vm');
            const addresses = require(__ADDRESSES__);
            const aliases = require(__ALIASES__).aliases;
            const template = fs.readFileSync(__HOME_SCRIPT__, 'utf8');
            const escapeSource = template.match(
                /function escapeHtml\(value\) \{[\s\S]*?\n\t\}/
            )[0];
            const context = {
                ClaudevilleAddresses: addresses,
                raw: '<img src=x onerror=alert(1)> Walk to Academia de Agentes',
                result: null,
            };
            addresses.setAliases(aliases);
            vm.createContext(context);
            vm.runInContext(
                `${escapeSource}; result = escapeHtml(` +
                `ClaudevilleAddresses.translateText(raw));`,
                context
            );
            console.log(JSON.stringify({result: context.result}));
            """
        output = _run_node(
            node_source.replace("__ADDRESSES__", addresses)
            .replace("__ALIASES__", aliases_path)
            .replace("__HOME_SCRIPT__", home_script)
        )
        self.assertEqual(
            output["result"],
            "&lt;img src=x onerror=alert(1)&gt; Walk to Claudeville:Agent Academy",
        )

    def test_all_historical_agent_text_is_translated_at_display_boundaries(self):
        home = (TEMPLATE_ROOT / "home/main_script.html").read_text(encoding="utf-8")
        demo = (TEMPLATE_ROOT / "demo/main_script.html").read_text(encoding="utf-8")
        inspector = (TEMPLATE_ROOT / "home/inspector_script.html").read_text(
            encoding="utf-8"
        )

        for expression in (
            "ClaudevilleAddresses.translateText(state.currently || '')",
            "ClaudevilleAddresses.translateText(state.action || '--')",
            "ClaudevilleAddresses.translateText(item.task)",
            "ClaudevilleAddresses.translateText(goal.title)",
            "ClaudevilleAddresses.translateText(memory.description)",
        ):
            self.assertIn(expression, inspector)
        self.assertIn(
            "actionEl.textContent = ClaudevilleAddresses.translateText(persona.action)",
            home,
        )
        self.assertIn(
            'ClaudevilleAddresses.translateText(description_content.split("@")[0])',
            home,
        )
        self.assertIn(
            "const displaySpeaker = ClaudevilleAddresses.translateText(speaker)", home
        )
        self.assertIn(
            "const displayLine = ClaudevilleAddresses.translateText(line)", home
        )
        self.assertIn("escapeHtml(displaySpeaker)", home)
        self.assertIn("escapeHtml(displayLine)", home)

        self.assertIn(
            'ClaudevilleAddresses.translateText(description_content.split("@")[0])',
            demo,
        )
        self.assertIn(
            "escHtml(ClaudevilleAddresses.translateText(chat_content_raw[j][0]))",
            demo,
        )
        self.assertIn(
            "escHtml(ClaudevilleAddresses.translateText(chat_content_raw[j][1]))",
            demo,
        )

    def test_home_uses_one_manifest_renderer_and_no_primary_flat_background_branch(self):
        main = (TEMPLATE_ROOT / "home/main_script.html").read_text(encoding="utf-8")
        home = (TEMPLATE_ROOT / "home/home.html").read_text(encoding="utf-8")
        inspector = (TEMPLATE_ROOT / "home/inspector_script.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("ClaudevilleWorld.queueWorld", main)
        self.assertIn("ClaudevilleWorld.createWorld", main)
        self.assertIn("worldManifest.resident_manifest_url", main)
        self.assertNotIn(
            'static_asset_root + "assets/characters/manifest.json"', main
        )
        self.assertNotIn('curr_maze === "the_ville"', main)
        self.assertNotIn('this.load.image("world_bg"', main)
        self.assertNotIn('this.add.image(0, 0, "world_bg")', main)
        self.assertIn("js/world_renderer.js' %}?v=", home)
        self.assertIn("js/world_addresses.js", home)
        self.assertIn("ClaudevilleAddresses.displayAddress", main)
        self.assertIn("ClaudevilleAddresses.displayAddress", inspector)
        self.assertIn(
            "ClaudevilleWorld.zoomCameraAtPointer(camera, pointer, zoomLevel);", main
        )

    def test_frozen_home_replay_does_not_poll_the_live_event_feed(self):
        main = (TEMPLATE_ROOT / "home/main_script.html").read_text(encoding="utf-8")
        feed = (TEMPLATE_ROOT / "home/feed_script.html").read_text(encoding="utf-8")

        self.assertIn("const IS_REPLAY = SIM_MODE === 'replay';", main)
        self.assertIn(
            "if (!IS_REPLAY) {\n\t\tpollFeed();\n\t\tsetInterval(pollFeed, POLL_MS);\n\t}",
            feed,
        )
        self.assertIn("window.feedChatLine = function", feed)

    def test_hidden_utility_keeps_replay_onboarding_and_components_closed(self):
        css = (STATIC_ROOT / "css/style.css").read_text(encoding="utf-8")
        hud_css = (STATIC_ROOT / "css/game_hud.css").read_text(encoding="utf-8")
        hud_js = (STATIC_ROOT / "js/hud_drawers.js").read_text(encoding="utf-8")
        home = (TEMPLATE_ROOT / "home/home.html").read_text(encoding="utf-8")
        main = (TEMPLATE_ROOT / "home/main_script.html").read_text(encoding="utf-8")

        self.assertIn(".hidden {\n  display: none !important;\n}", css)
        self.assertIn('id="first-run-hint" class="ui-overlay first-run-hint hidden"', home)
        self.assertNotIn('id="replay-badge"', home)
        self.assertIn("if (!IS_REPLAY && !localStorage", main)
        self.assertNotIn("getElementById('replay-badge')", main)
        self.assertIn("Replay · frozen step", main)
        self.assertIn("side-panel collapsed", home)
        self.assertIn("event-feed collapsed", home)
        self.assertIn('aria-expanded="false"', home)
        self.assertIn("js/hud_drawers.js", home)
        self.assertIn(".hud-secondary-drawer.hud-open", hud_css)
        self.assertIn("blocksCameraInput", hud_js)
        self.assertIn(".menu-overlay.hidden", css)
        self.assertIn(".chat-popup.hidden", css)
        self.assertIn("transition: opacity 0.2s ease", css)
        self.assertIn("transition: opacity 0.3s ease", css)

    def test_smooth_demo_uses_manifest_renderer_and_display_time_aliases(self):
        demo = (TEMPLATE_ROOT / "demo/demo.html").read_text(encoding="utf-8")
        script_path = TEMPLATE_ROOT / "demo/main_script.html"
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("js/world_renderer.js' %}?v=", demo)
        self.assertIn("js/world_addresses.js", demo)
        self.assertIn("ClaudevilleWorld.queueWorld", script)
        self.assertIn("ClaudevilleWorld.createWorld", script)
        self.assertIn("worldManifest.resident_manifest_url", script)
        self.assertNotIn(
            'static_asset_root + "assets/characters/manifest.json"', script
        )
        self.assertIn("ClaudevilleAddresses.displayAddress", script)
        self.assertNotIn('curr_maze === "the_ville"', script)
        self.assertNotIn('this.load.image("world_bg"', script)
        self.assertLess(len(script.splitlines()), 500)

    def test_demo_stage_is_scoped_scrollable_and_home_stays_full_screen(self):
        demo = (TEMPLATE_ROOT / "demo/demo.html").read_text(encoding="utf-8")
        home = (TEMPLATE_ROOT / "home/home.html").read_text(encoding="utf-8")
        base = (TEMPLATE_ROOT / "base.html").read_text(encoding="utf-8")
        global_css = (STATIC_ROOT / "css/style.css").read_text(encoding="utf-8")

        self.assertIn("{% block extra_head %}", base)
        self.assertIn('class="demo-replay-page"', demo)
        self.assertIn("html, body {", demo)
        self.assertIn("overflow-y: auto", demo)
        self.assertIn("background: #f4f4f0", demo)
        self.assertIn("color: #1f2937", demo)
        self.assertIn(".demo-replay-page #game-container {", demo)
        self.assertIn("position: relative", demo)
        self.assertIn("background: #1a1a2e", demo)
        self.assertIn("max-width: 1200px", demo)
        self.assertIn("aspect-ratio: 1200 / 640", demo)
        self.assertIn(".demo-replay-page #game-container > canvas {", demo)
        self.assertIn("@media (max-width: 768px)", demo)
        self.assertNotIn("pointer-events: none", demo)

        self.assertNotIn("demo-replay-page", home)
        self.assertIn("#game-container {", global_css)
        self.assertIn("position: fixed", global_css)


class RecordedWorldSelectionTests(SimpleTestCase):
    def test_frozen_replay_uses_each_recordings_stored_world(self):
        for maze_name, expected_path in (
            ("claudeville", "assets/claudeville/world.json"),
            ("the_ville", "assets/the_ville/world.json"),
        ):
            with self.subTest(maze_name=maze_name):
                with (
                    mock.patch(
                        "translator.views.load_replay_snapshot",
                        return_value={
                            "requested_step": 5,
                            "effective_step": 5,
                            "environment": {"Nora Vale": {"x": 1, "y": 2}},
                            "persona_names": ["Nora Vale"],
                            "meta": {"maze_name": maze_name},
                        },
                    ) as load_snapshot,
                    mock.patch("translator.views.render") as render,
                ):
                    views.replay(RequestFactory().get("/replay/run/5/"), "run", 5)

                context = render.call_args.args[2]
                self.assertEqual(context["maze_name"], maze_name)
                self.assertEqual(context["world_manifest_path"], expected_path)
                load_snapshot.assert_called_once_with(views.settings.BASE_DIR, "run", 5)
