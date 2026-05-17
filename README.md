# RogueTech

A total conversion mod for [HBS BattleTech](https://harebrained-schemes.com/battletech/). RogueTech expands the base game with new factions, mechs, weapons, equipment, events, star systems, and an ongoing persistent war map — turning the campaign into a living Inner Sphere.

**Upstream repo:** [BattletechModders/RogueTech](https://github.com/BattletechModders/RogueTech)  
**Wiki:** [roguetech.fandom.com](https://roguetech.fandom.com/wiki/RogueTech_Wiki)  
**Discord:** [discord.gg/roguetech](https://discord.gg/roguetech)

---

## For players

RogueTech is installed via the **RogueTech Launcher** (RogueLauncher.exe), distributed through the [Discord server](https://discord.gg/roguetech). The launcher downloads and installs the mod pack automatically.

**Linux users:** see [RogueTechLinuxInstall](https://github.com/BattletechModders/RogueTechLinuxInstall) for a Wine-based setup script.

---

## For modders and contributors

This is a pure data repository — no C# code, no build step. All content is JSON.

### Repository structure

```
Core/               — 100+ bundled mods, each in its own subdirectory with a mod.json
DLC/                — HBS DLC extension mods
Eras/               — Era packs (ClanInvasion3061, CivilWar3062-3067, etc.)
InstallOptions/     — User-selectable install options (settings-only mod fragments)
Optionals/          — Optional content packs
ModTek/             — Bundled ModTek runtime
RtConfig.xml        — RogueTech launcher configuration
```

The repo contains **37,900+ JSON files** covering BattleTech def types: `mechdef`, `chassisdef`, `vehicledef`, `vehiclechassisdef`, `starsystemdef`, `lancedef`, `pilot`, `event`, `turretdef`, `turretchassisdef`, and ModTek `mod.json` manifests.

### Validation

All JSON files must pass the validation script before merging. CI runs this automatically on every push and PR to `Dev`.

```bash
# Validate all JSON files
python .github/scripts/validate_json.py

# Validate only staged files (pre-commit hook, fast)
git config core.hooksPath .githooks

# Fix common syntax errors (trailing commas, JSONC comments) in known-bad files
python .github/scripts/fix_json_errors.py
```

The validator checks:
- JSON syntax and duplicate keys
- Required fields for each BattleTech def type (by filename prefix)
- `Description.Id` uniqueness per def type
- `mod.json` files for required `Name` field (skips settings-only fragments)

### Contributing

1. Fork to your own GitHub account and work on a feature branch.
2. Run `python .github/scripts/validate_json.py` locally before opening a PR.
3. Open PRs against the `Dev` branch.

Common pitfalls:
- **Trailing commas** — invalid in JSON; use the fix script or your editor's JSON formatter.
- **Duplicate keys** — the validator catches these; usually a copy-paste artifact.
- **`Description.Id` collisions** — IDs must be unique per def type across the whole repo.
