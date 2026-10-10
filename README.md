<img width="1920" height="1080" alt="thumbnail" src="https://github.com/user-attachments/assets/a3a2c8f7-4444-43fd-bce7-505fe5d0d2ee" />

# Better Chat

A Helldivers 2 Lua mod for [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) that plays a sound when another player sends a chat message, lets you resize the text chat, adds Ctrl+V paste to the chat, and can translate other players' messages.

## Features

- **Sound Alert in Ship / Sound Alert in Mission:** when another player's chat message arrives, one of the game's own sounds plays, at most once every 2 seconds, chosen separately for the ship and for missions. Choose OFF, Player Joined (default), Player Left, Menu Tab, Menu Subtab, Option Click, or one of five louder sounds: Menu Confirm, Menu Back, Action Wheel, Item Purchase and Confirmation Dialog. The mission setting also offers two sounds the game only has in missions: Reinforce Request (the sound of a dead player asking to be reinforced) and Countdown. Applying a sound in the menu plays it once so you can hear it.
- **Sound Alert on My Messages:** off by default. Your own messages also play the sound, so you can try the sounds alone. Messages from players you muted never make a sound.
- **Chat Size (%):** from 50 to 200% (default 100), makes the text chat and its text bigger or smaller.
- **Paste (Ctrl+V):** while you type in the chat, Ctrl+V adds the copied text after what you already typed, up to the chat's own length limit. Line breaks become spaces; emoji are left out.
- **Translate Chat (highly experimental):** off by default. See [Chat translation](#chat-translation-highly-experimental) below.
- The settings are in [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) (escape menu > MODS > Better Chat). Without it, the Player Joined sound plays, the chat keeps the game's size, paste works and translation stays off.
- The settings' names follow the game's Text Language.

## Chat translation (highly experimental)

When **Translate Chat** is on, each message from another player is translated, and the translation is added to your chat right below the original, under the same player's name, starting with the language it came from (for example `[EN] ...`). The original message always stays.

- **Only you see the translations.** They are added to your own chat on your own PC; nothing is sent to the other players, and they still see only the original message.
- **Translate To** picks the language: **Automatic** (default) uses the language of your Windows regional format (Settings > Time & language > Language & region), which is often your own language even when Windows or the game is in English; **Game Language** uses the game's Text Language; or pick one of the game's languages. Messages already in that language are not translated.
- **Translate My Messages** (off by default) also translates your own messages, so you can try translation alone.
- Very short messages written only in Latin letters (fewer than 4 letters, like "gg", "o7" or "ez") are not translated: they would be mistaken for other languages.

**What is sent, and to whom.** While Translate Chat is on, the text of each message from another player (and your own, with Translate My Messages) is sent to Google Translate at `translate.googleapis.com`, together with the language to translate into. No player names or game data are sent; like any web request, it comes from your internet connection, so Google sees your IP address. Nothing is sent while the option is off. The mod uses Google's keyless public endpoint through the `curl.exe` that ships with Windows, started in the background without a window. While the option is on, curl is also started once per session with nothing to do (nothing is sent), so that a slow first start does not stutter the game when a message arrives. Messages and translations are not written to the mod's log.

**Why highly experimental.**

- The endpoint is unofficial: Google can limit, change or close it at any time, and translation then stops working (the chat itself is unaffected).
- Each translation takes about half a second to a second and a half to arrive.
- Machine translation of short, slangy chat can be wrong or odd.
- It needs `curl.exe`, which Windows 10 (version 1803 and later) and Windows 11 include. It does not work on Linux or Steam Deck (Proton).
- It has been tested by a few players only.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Optional: [Mod Options Menu](https://www.nexusmods.com/helldivers2/mods/16625) for the settings.
3. Install the ZIP from [Releases](https://github.com/Alomare/BetterChat/releases) with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy. Keep Bingus Shared Loader last in the mod order, so it loads first.

The verdict is the first line of `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BetterChat_STATUS.log`.

## Technical Details

- **New messages.** The game keeps the chat's last 64 lines in a ring (first index, line count, then each line's sender, time and text). Every 200 ms the mod reads the ring's first index and count in one 8-byte read; when lines were added, it reads their senders and compares them with the local player's peer id. A new session or a cleared history only sets a new baseline. The game drops muted players' lines before they reach the ring.
- **The sounds.** Posted through the game's UI sound function. The first five sound ids are read from the game code that plays them: the HUD feed's player joined and left notices (with a ship and a mission variant), the menu tab bar's buttons, the standard menu button and an option row's arrow. The five louder sounds are given by the game's own id for them, which is a hash of the sound's name (the upper half of MurmurHash64A) and so stays the same across game updates; each exists in both of the game's UI sound banks, the ship's and the missions'. They were picked from a loudness survey of the game's UI sounds (`research/sound_survey.py`). Reinforce Request and Countdown are given the same way but exist only in the missions' bank, so only the mission setting offers them; Reinforce Request starts after a second of silence, as the game plays it. The game mode (ship or mission) picks which setting applies. The 2-second cooldown counts the frame time the game passes to the Lua update.
- **The size.** The chat widget is found inside the HUD and scaled with the game's own widget scale setter, relative to its own scale. It is checked every 30 frames, so a rebuilt HUD (after loading) gets the size again; a widget not laid out yet is left alone.
- **Paste.** On Ctrl+V (Windows' key state, with the game window in front) while the chat widget's text input is open (its open flag is read every 100 ms; the keys are read only while it is open, since Windows' key state call can take several milliseconds), the clipboard's Unicode text is cleaned (line breaks and tabs to one space, other control characters and characters outside the Basic Multilingual Plane left out), added to the field's current text, cut to the field's own character limit on character boundaries, and set through the game's text widget setter, the same call the game uses for Steam's text input.
- **Translation.** Windows' `curl.exe` requests `translate.googleapis.com/translate_a/single` with automatic source detection. Its command line is always `curl.exe -K -`: the request (address, options and the line, quoted and escaped so a line can't add options) goes in through its standard input as a curl config, so the line is never on a command line, and no address is either (the first start of a curl with an address on its command line took a few hundred milliseconds in the game). curl runs without a window and receives only its own pipe ends, and its reply is read from a pipe every frame, so the game only waits for curl to start (a few milliseconds). curl is also started once in advance, as soon as Translate Chat is on (while the game loads, or when you turn it on in the menu), with an empty config: it exits at once and sends nothing. One request at a time (up to 8 lines wait), a server or network error is retried once, a request still running after 12 seconds is ended. The reply's detected language is compared with the target (Brazilian and European Portuguese count as one language; Simplified and Traditional Chinese don't). A translation is added through the game's own chat add-line, under the original sender, which only adds the line to the local chat; the added line is taken as the new baseline, so it makes no sound and is never translated again.
- **Finding the game's code.** Every global, native function and structure offset, and the first five sound ids, come from 16 code signatures generated in one block by `research/signatures.py` from a game.dll dump and checked to match exactly once. Each is tried at the known build's address first, else game.dll's executable sections are searched over a few frames; values are read from the matched instructions and repeated values must agree. Without the chat's code the mod turns off; without a sound's, the size's, paste's or the add-line's code, only that part does. The search engine (`tools/sigscan.lua` in the author's workspace) is shared with the author's other mods.
- **Texts.** `locales/en.lua` is the English source and `locales/<tag>.lua` the bundled translations, resolved by CowboyBingus' `src/bingus_text.lua` against the game's Text Language; the build places both ahead of the script.
- **Diagnostics.** An update of the mod that takes more than 4 ms is written to the log with the time of each part (at most 40 per session).
- **Memory access.** Reads go through `ReadProcessMemory` on the game's own process, which fails instead of crashing on a bad address. The mod never writes game memory itself; the game's own functions play the sound, set the size, set the pasted text and add the translations.
- **Tests.** `tests/test_release.py` runs the built entry under LuaJIT against a game.dll dump (not included), with the chat ring, the HUD, the game's sound, scale, text and add-line functions, curl, the clipboard and Mod Options Menu simulated.

Research notes: [NOTES.md](NOTES.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Credits

- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus, whose `bingus_text.lua` provides the translations.
- Developed with Claude Opus 5.5 and the [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill).
