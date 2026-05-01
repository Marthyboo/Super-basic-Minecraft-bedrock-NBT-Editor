# Bedrock `level.dat` Editor

## What it edits

- World name
- Game mode
- Difficulty
- Seed
- Spawn position
- Common gamerules and ability flags
- Raw NBT values from the same `level.dat`

## What it does not edit

- The rest of the Bedrock save under `db\`

That data is LevelDB, not plain NBT, so this tool is focused on the actual world-settings file: `level.dat`.

## Run it

Double-click:

- `run_bedrock_nbt_editor.bat`

Or run:

```powershell
python .\bedrock_nbt_editor.py
```

## Notes

- The script auto-loads the first `level.dat` it finds under the current folder.
- Every save creates a timestamped backup next to the real file, like `level.dat.bak.20260501_123456`.
- Use `Apply Fields` for the left-side quick settings.
- Use `Re-enable Achievements` to set these NBT flags to `0`:
  `experiments_ever_used`, `saved_with_toggled_experiments`, `hasBeenLoadedInCreative`,
  `experiments.experimental_creator_cameras`, `experiments.gametest`,
  and `experiments.upcoming_creator_features`.
- Use `Apply Selected Value` after changing something in the raw tree editor.
- The button applies changes in memory. Click `Save` to write them to `level.dat`.
- On this specific world, `commandsEnabled` and `experimentalgameplay` are still `1`, so the button warns about those as possible remaining blockers.
