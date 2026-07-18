"""Focused contracts for collision-aware historical replay rendering."""

from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from .test_world_renderer import _run_node

COLLISION = Path(__file__).resolve().parents[1] / "static_dirs/js/world_collision.js"


class WorldCollisionTests(SimpleTestCase):
    def test_projector_moves_only_blocked_legacy_tiles(self):
        result = _run_node(
            f"""
            const collision = require({json.dumps(str(COLLISION))});
            const empty = {{index: -1}}, solid = {{index: 0}};
            const data = Array.from({{length: 4}}, () => Array(4).fill(empty));
            data[0][0] = solid;
            const manifest = {{dimensions: {{width: 2, height: 2}},
              visual_dimensions: {{width: 4, height: 4}}, collision_layer: 'Collisions'}};
            const projector = collision.createProjector(
              {{layers: [{{name: 'Collisions', data}}]}}, manifest
            );
            console.log(JSON.stringify({{
              blocked: projector.isBlocked(0, 0),
              projected: projector.project([0, 0]),
              unchanged: projector.project([1, 1])
            }}));
            """
        )
        self.assertTrue(result["blocked"])
        self.assertEqual(result["projected"], [1, 0])
        self.assertEqual(result["unchanged"], [1, 1])
