<img width="1920" height="1080" alt="thumbnail" src="https://github.com/user-attachments/assets/a3a2c8f7-4444-43fd-bce7-505fe5d0d2ee" />

# Better Chat

A Helldivers 2 Lua mod for [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) that plays a sound when another player sends a chat message, and lets you resize the text chat.

## Features

- **New Message Sound:** when another player's chat message arrives, one of the game's own sounds plays, at most once every 2 seconds. Choose OFF, Player Joined (default), Player Left, Menu Tab, Menu Subtab or Option Click. Applying a sound in the menu plays it once so you can hear it.
- Your own messages and messages from players you muted make no sound.
- **Chat Size (%):** from 50 to 200% (default 100), makes the text chat and its text bigger or smaller.
- Both settings are in [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) (escape menu > MODS > Better Chat). Without it, the Player Joined sound plays and the chat keeps the game's size.
- The settings' names follow the game's Text Language.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Optional: [Mod Options Menu](https://www.nexusmods.com/helldivers2/mods/16625) for the settings.
3. Install the ZIP from [Releases](https://github.com/Alomare/BetterChat/releases) with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy. Keep Bingus Shared Loader last in the mod order, so it loads first.

The verdict is the first line of `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BetterChat_STATUS.log`.

## Technical Details

- **New messages.** The game keeps the chat's last 64 lines in a ring (first index, line count, then each line's sender, time and text). Every 200 ms the mod reads the ring's first index and count in one 8-byte read; when lines were added, it reads their senders and compares them with the local player's peer id. A new session or a cleared history only sets a new baseline. The game drops muted players' lines before they reach the ring.
- **The sounds.** Posted through the game's UI sound function. Every sound id is read from the game code that plays it: the HUD feed's player joined and left notices (with a ship and a mission variant), the menu tab bar's buttons, the standard menu button and an option row's arrow. The 2-second cooldown counts the frame time the game passes to the Lua update.
- **The size.** The chat widget is found inside the HUD and scaled with the game's own widget scale setter, relative to its own scale. It is checked every 30 frames, so a rebuilt HUD (after loading) gets the size again; a widget not laid out yet is left alone.
- **Finding the game's code.** Every global, native function, structure offset and sound id comes from 11 code signatures generated in one block by `research/signatures.py` from a game.dll dump and checked to match exactly once. Each is tried at the known build's address first, else game.dll's executable sections are searched over a few frames; values are read from the matched instructions and repeated values must agree. Without the chat's code the mod turns off; without a sound's or the size's code, only that part does. The search engine (`tools/sigscan.lua` in the author's workspace) is shared with the author's other mods.
- **Texts.** `locales/en.lua` is the English source and `locales/<tag>.lua` the bundled translations, resolved by CowboyBingus' `src/bingus_text.lua` against the game's Text Language; the build places both ahead of the script.
- **Memory access.** Reads go through `ReadProcessMemory` on the game's own process, which fails instead of crashing on a bad address. The mod never writes game memory itself; the game's own functions play the sound and set the size.
- **Tests.** `tests/test_release.py` runs the built entry under LuaJIT against a game.dll dump (not included), with the chat ring, the HUD, the game's sound and scale functions and Mod Options Menu simulated.

Research notes: [NOTES.md](NOTES.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Credits

- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus, whose `bingus_text.lua` provides the translations.
- Developed with Claude Opus 5.5 and the [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill).
