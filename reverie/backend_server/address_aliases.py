"""Canonical reverse-address index with versioned legacy input aliases."""

from __future__ import annotations

import json
from pathlib import Path


def load_address_aliases(
    path: Path, *, required: bool = False, expected_world: str | None = None
) -> dict[str, str]:
    """Load a validated v1 manifest, failing closed when it is declared."""
    if not path.is_file():
        if required:
            raise FileNotFoundError(
                f"required address alias manifest is missing: {path}"
            )
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"unsupported address alias schema: {path}")
    if expected_world is not None and payload.get("world") != expected_world:
        raise ValueError(
            f"address alias manifest world does not match {expected_world}: {path}"
        )
    aliases = payload.get("aliases")
    if not isinstance(aliases, dict):
        raise ValueError(
            f"address alias manifest must contain an aliases object: {path}"
        )

    validated = {}
    for legacy, canonical in aliases.items():
        if not isinstance(legacy, str) or not legacy.strip():
            raise ValueError(f"address alias keys must be non-empty strings: {path}")
        if not isinstance(canonical, str) or not canonical.strip():
            raise ValueError(f"address alias values must be non-empty strings: {path}")
        validated[legacy] = canonical
    return validated


def canonicalize_address(address: str, aliases: dict[str, str]) -> str:
    """Return a canonical address, replacing the longest matching prefix."""
    if not isinstance(address, str):
        raise TypeError("address must be a string")
    for legacy in sorted(aliases, key=len, reverse=True):
        if address == legacy or address.startswith(f"{legacy}:"):
            return f"{aliases[legacy]}{address[len(legacy) :]}"
    return address


class AddressTileIndex(dict):
    """Canonical-key dictionary whose lookup boundary accepts legacy aliases."""

    def __init__(self, aliases: dict[str, str] | None = None):
        super().__init__()
        self._aliases: dict[str, str] = {}
        if aliases:
            self.set_aliases(aliases)

    def set_aliases(self, aliases: dict[str, str]) -> None:
        """Install aliases only when every target is an existing canonical key."""
        unknown = sorted(
            target for target in aliases.values() if not dict.__contains__(self, target)
        )
        if unknown:
            raise ValueError(
                f"address aliases target unknown canonical addresses: {unknown}"
            )
        self._aliases = dict(aliases)

    def canonicalize(self, address: str) -> str:
        return canonicalize_address(address, self._aliases)

    def __contains__(self, address):
        if not isinstance(address, str):
            return False
        return super().__contains__(self.canonicalize(address))

    def __getitem__(self, address):
        return super().__getitem__(self.canonicalize(address))

    def get(self, address, default=None):
        if not isinstance(address, str):
            return default
        return super().get(self.canonicalize(address), default)


def _addresses_for(tile: dict) -> list[str]:
    world, sector = tile["world"], tile["sector"]
    addresses = []
    if sector:
        addresses.append(f"{world}:{sector}")
    if tile["arena"]:
        addresses.append(f"{world}:{sector}:{tile['arena']}")
    if tile["game_object"]:
        addresses.append(f"{world}:{sector}:{tile['arena']}:{tile['game_object']}")
    if tile["spawning_location"]:
        addresses.append(f"<spawn_loc>{tile['spawning_location']}")
    return addresses


def build_address_tile_index(
    tiles: list[list[dict]],
    *,
    world_root: Path,
    manifest_name: str | None,
    expected_world: str,
) -> AddressTileIndex:
    """Build canonical reverse lookup, then validate and install declared aliases."""
    index = AddressTileIndex()
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            raise ValueError("maze tile rows must be lists")
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                raise ValueError("maze tiles must be objects")
            for address in _addresses_for(tile):
                index.setdefault(address, set()).add((x, y))

    if manifest_name is None:
        return index
    if (
        not isinstance(manifest_name, str)
        or not manifest_name
        or Path(manifest_name).name != manifest_name
    ):
        raise ValueError("address_alias_manifest must be a plain file name")
    aliases = load_address_aliases(
        world_root / manifest_name,
        required=True,
        expected_world=expected_world,
    )
    index.set_aliases(aliases)
    return index
