# Better Chat: research notes

Goal: quality of life for the text chat, each part a Mod Options Menu setting: a sound when another player's message arrives (one of the game's UI sounds, at most once every 2 s) and the chat box's size. A taskbar flash, chat position and unfiltered messages were tried in the test builds and dropped (see Recon 1 and 2).

All addresses are game.dll RVAs for build 25480438 (Ghidra's session base is 0x7ffcea020000). Decompiles: `_research/chat/` (`send.c`, `recv.c`, `ui.c`, `filter.c`, `notify_sounds.c`). Signatures: `research/signatures.py`.

## How the chat works (offline)

- **Chat object:** network context `[0x347cef0]` + 0xc418. Byte +0 = text chat enabled (add-line returns at once when 0).
- **History ring:** 64 lines of 0x228 bytes from chat + 0xb90; first index at +0x9590, count at +0x9594 (count stops at 64, then the first index advances; both zeroed by the reset 0x1097010). Line: +0 time (u64), +8 sender peer id (u64), +0x10 UTF-8 text (0x201 bytes), +0x211 friend, +0x212/+0x213 filter state, +0x214/+0x215 display flags, +0x220 platform (int).
- **Add-line `0x10979c0(chat, sender, text)`:** called by the chat box send `0x1097560` (your own lines, sender = local peer at context + 0xb398) and the two RPC receive handlers `0xb954b0`, `0xbb6210` (+ `0x1097c90`). A line from a player the chat doesn't know, or one muted/blocked (`0x13e5220`), is dropped before the ring. It ends with the HUD notice `0x12f2f60`.
- **HUD notice `0x12f2f60(_, sender, text)`:** formats "<name>: text" (0x1c12037f) into the chat widget (`[0x346d538]` + 0x14498) through `0x185f470`, then for anyone but the local player calls the UI sound `0x1327f50` with id 0 (plays nothing): the game has an empty received-message sound slot.
- **UI sound `0x1327f50(unused, id)`:** game hash -> Wwise id through the runtime map (see ImpatientDiver NOTES). Chat's own ids: open 0x74ef3f93, close 0x5d5ed59c, send 0xe1ba68c0. HUD feed "player joined" `0x12f21e0`: 0xda653421 on the ship, 0x82250982 in missions; "player left" `0x12f26b0`: 0xc386a64a / 0x3cf15e0. Game mode: `[0x3326340]` + 0xac21c (3 ship, 4 mission). Every id passed directly to the sound function was harvested (about 330); none could be named from the hash lists.
- **Menu sounds:** the game's standard button sound record (init `0x14a47d0`): hover +4 0x65e34ad8, click +8 0x468c8e58 (copied into many menus' buttons, e.g. `0x1499240`). The menu tab bar (`0x17aac50` sets its labels; up to 8 tabs of 0xd48 bytes) is made of buttons of class `0x17af630` (states 0-9 at +0xd20), whose init `0x17ae3xx` sets hover +0xd40 = 0x78e15850 and click +0xd44 = 0xadd37058 (state 4 plays +0xd40, states 6 and 8 play +0xd44); `0x17af010` and `0x17ab300` set them but have no direct callers. An option row's arrow (`0x17fdd30`, `0x17fde75`) plays 0x144418d5 when the value changes, 0x3e8c63db when it can't. The OPTIONS content plays 0x468c8e58 on APPLY (Mod Options Menu uses it for its APPLY too). Menu open/close are 0x400d9983 / 0x702f7ffb plus mix states (`0x1455840`, `0x1459140`).
- **Text filter:** platform object `[0x3326e48]` + 0x2494 (byte), set at platform init (`0x13e7d50`) from a platform service call. When set, add-line hands another player's text to the platform filter (`[[engine + 0x148] + 0x58] + 0x10`, mode 2); when 0, it copies the text as typed. Also read where player names (0x80-byte strings) are copied, likely the lobby members (`0x1095620`) and by two filter callbacks. Own lines are never filtered.

## The chat widget (offline)

The chat HUD widget is `[0x346d538]` + 0x14498 (its active byte is the HUD's +0x24e335). Its update `0x185fd10`:

- Docked (some UI states) or not: when the docked state changes (+0x139be) it fades out, then applies position, anchor and pivot: docked (0, -20), (0.5, 1), ...; undocked its own fields +0x139a0 (position), +0x139a8 (anchor), +0x139b0 (pivot), through set_position `0x14476a0`, set_anchor `0x144f160`, set_pivot.
- In missions (mode 4, `[0x346d530]` + 0x190c != 6) it sets the position every frame to the field plus (0, something * 433).
- Height: the line stack plus 66, clamped to 40..185 (rdata constants), width 400. More visible lines would need those constants changed (read-only data): not done.
- `0x1860930` (store +0x139a0) and `0x1860910` (set_scale(s, s)) exist with no callers: the game never scales the chat. Widget layout: position +4/+8, size +0xc/+0x10, scale +0x14/+0x18 (set_scale `0x1447ed0` compares those).

## Recon 1 (live, 2026-10-05)

- The sound works for other players' messages. "Message Sent" (the chat's send sound 0xe1ba68c0) is mute when posted from the mod: dropped.
- Taskbar flash: dropped by the user.
- Chat position: dropped by the user (in missions the minimap displaces the chat). The game's own position field read (-36, 81). Code removed in recon 2 (field +0x139a0 and set_position, see above).
- Size: works.
- Text filter: the flag is 1 on Steam, yet swear words between two Steam players arrived unfiltered, so the platform filter leaves PC text alone. Untested with console (PSN) players.

## Recon 2 (live, 2026-10-06)

- The Menu Tab, Menu Subtab and Option Click choices (0xadd37058, 0x468c8e58, 0x144418d5) are the right sounds, confirmed by the user; the Sound Test was removed.
- Show Unfiltered Messages: dropped by the user as redundant (Steam already shows chat unfiltered). The flag (`[0x3326e48]` + 0x2494) stays documented above.

## Design (V1)

- **Detection:** every 200 ms of frame time (V2; every frame in V1) one 8-byte read of the ring header; new lines = count change + first index change (mod 64); a lower count or another context resets the baseline (no sound for lines already there). Each new line's sender is compared with the local peer id. Your own lines don't alert; muted players' lines never reach the ring.
- **Sound:** choice OFF / Player Joined (default) / Player Left / Menu Tab / Menu Subtab / Option Click, every id read from the code that plays it (the HUD notices with a mission and a ship variant by game mode); 2 s cooldown (frame time). Applying a sound in the menu plays it once. A choice whose signature is missing plays nothing.
- **Size:** set_scale(widget, base * size%), base = the widget's own scale before the mod changed it; re-applied every 30 frames (a new HUD layout resets it), nothing while the widget's scale is 0 (not laid out).
- The mod never writes game memory itself: reads go through ReadProcessMemory; the sound and the size go through the game's own functions.
- Texts: 10 keys in `locales/`, 13 translations using the game's own word for Text Chat.

## Alert volume (offline, 2026-10-06)

Request: a volume setting for the new message sound. Decompiles: `_research/chat/volume/` (`ui_sound.c`, `flow.c`, `flow_source.c`, `audio_calls.c`, `settings.c`).

- **The UI sound function `0x1327f50(_, id)` is three engine calls:** `source = [engine + 0x288](wwise_world)`, `event = 0x12556e0(id)` (game sound hash -> Wwise event id), `[engine + 0x338](wwise_world, event, source, 0)`. `engine` = `[0x3326318]`, the engine's script function table (helldivers2.exe functions, 2137 references in game.dll); `wwise_world` = `[[0x3326340] + 0x10f8]`. So every UI sound plays on a new sound source of its own (a Wwise game object): a per-source level changes that one sound and nothing else. A sibling `0x4dcbc0` does the same through `+0x1e8`.
- **Engine table entries named by the game's native Wwise flow callbacks** (`0xfc5550` replaces `WwiseFlowCallbacks.wwise_trigger_event`, `wwise_make_auto_source` and `wwise_make_manual_source` with native code: `0xfc4c50`, `0xfc51d0`): `[0]` the invalid source id; +0x58 `wwise_world(world)`; +0x288 make source `(ww)`; +0x298 make source at a pose `(ww, matrix, debug name)`; +0x2a0 make source on a unit `(ww, unit, node)`; +0x2a8 a unit's existing source (0xffffffff = none); +0x2e8 set manual `(ww, source, bool)`; +0x2f0 is manual; +0x338 trigger event `(ww, event id, source, 0)` -> playing id; +0x458 `(ww, source, bool, float)` called after every positioned source with (1, 1.0), meaning unknown. From other callers: +0x380 source parameter (RTPC) `(ww, source, parameter id, value)`; +0x3a0 / +0x3a8 environment (aux bus) by name / by id `(ww, bus, value)`; +0x2e0 `(ww, source, seconds)`; +0xa0 / +0x1b8 / +0x1c0 global parameters by name / id.
- **A per-source level exists in the engine's Lua API, not in game.dll:** the game's own `core/wwise/lua/wwise_flow_callbacks` (bytecode in the game data) uses `stingray.Wwise.wwise_world(world)` and `stingray.WwiseWorld.set_dry_environment_for_source(wwise_world, source_id, value)` (plus `set_source_parameter`, `make_manual_source`, `trigger_event`...). In Stingray the dry level is Wwise's `SetGameObjectOutputBusVolume` (a linear gain on that game object's output: 0 silence, 1 unchanged; above 1 amplifies in recent Wwise versions unless the engine clamps it). game.dll never calls that table entry, and the Lua binding names are in helldivers2.exe (no dump), so its table offset is unknown: the mod calls it through Lua.
- **Lua cannot post these events itself:** `WwiseWorld.trigger_event` takes event names, and the game only has ids (its own hash -> Wwise id map). So the plan mixes both: native make source and post (as the UI sound function does), Lua for the level in between. Lua's Wwise world is matched to the native one by address (`string.format('%p', ...)` on the lightuserdata).
- **The player's volume settings** (`audio_volume`, `dialogue_volume`, `music_volume`, `sfx_volume`, `voice_chat_volume`, `tts_volume`: floats at the start of the settings object, read by `0x102c9c0`) are global; nothing per sound.
- **Sound bank editing** (the fallback): changing the event's sound volume in its Wwise bank needs a data patch, changes that sound everywhere the game plays it (the join notice, the menu clicks) and gives one fixed volume per installed patch, not a slider. Only worth it if the source level fails.

## Recon 2-1 (live, 2026-10-06): volume not released

Test build `Better-Chat-2-recon-1` (script kept as `research/recon_volume_1.lua`): a New Message Volume slider (25-400%) doing make source, `set_dry_environment_for_source(lua wwise world, source, level)`, post event; a test toggle played volumes above 100% as several copies.

- **Result: the level was never set.** The mod could not match Lua's Wwise world to the native one (`0x25d44c00080`): `Wwise.wwise_world(world)` returns a full userdata (Lua heap addresses such as `0x7e85e688`, one per world, 12 worlds), so `%p` gives the box, not the Wwise world. Every play fell back to the game's sound function, which is why the user heard no change. Whether the dry level changes the volume is still unknown.
- No crash: `Application.main_world`, `Application.worlds` and `Wwise.wwise_world` on all 12 worlds are safe on the ship.
- **Lua API (live):** `Wwise`: duration_type, has_event, load_bank, max_attenuation, max_duration, min_duration, position_type, set_language, set_panning_rule, set_state, unload_bank, wwise_world. `WwiseWorld`: add_default_listeners, add_soundscape_listener, add_soundscape_unit_source, add_source_listeners, destroy_manual_source, enabled, get_playing_elapsed, has_source, is_playing, make_auto_source, make_manual_source, pause_all, pause_event, post_trigger, remove_default_listeners, remove_soundscape_listener, remove_soundscape_source, remove_source_listeners, reset_aux_environment, reset_environment_for_source, resume_all, resume_event, set_dry_environment, set_dry_environment_for_source, set_enabled, set_environment, set_environment_for_source, set_global_parameter, set_listener, set_source_lifetime, set_source_parameter, set_source_pose, set_source_position, set_switch, stop_all, stop_audio_input_sound, stop_event, trigger_audio_input_event, trigger_audio_input_sound, trigger_event, unlink_source.
- **Wwise event ids** (game id > Wwise id): joined ship 0xda653421 > 2625604776, mission 0x82250982 > 147058876; left ship 0xc386a64a > 3285929117, mission 0x03cf15e0 > 2669315291; tab 0xadd37058 > 3782250789; subtab 0x468c8e58 > 2156104120; option 0x144418d5 > 1540929694.
- **Decision (user):** no sound bank changes; V2 ships without a volume option. If it is tried again: find the native pointer inside the userdata (read its payload and compare with `[[0x3326340] + 0x10f8]`) to pick the right Lua Wwise world, then repeat the listening test.

## V2

No gap between the two options; the chat history is read every 200 ms of frame time instead of every frame.

## Chat translation (offline, 2026-10-06)

Request (a user comment): translate other players' chat messages. Design: opt-in, Google Translate's keyless endpoint through Windows' curl.exe, the translation added to the chat on this machine only.

- **Showing a line:** add-line `0x10979c0(chat, sender, text)` (`_research/chat/send.c`) only writes the ring and calls the HUD notice; the network send is the chat box's `0x1097560`, which calls add-line for your own lines. So calling add-line with another player's peer id adds a line under that player's name only for you. It drops the line when the sender is no longer in the session, muted or blocked. It copies the text with a bounded copy into 0x201 bytes (a text of 0x201 bytes or more must never reach it): the mod cuts at 0x1f0 bytes on a UTF-8 boundary. Another player's text also goes through the platform filter (the flag in the text filter section); your own does not. Signature `add_line` (13 unique bytes, 28 used); `chat_ring` starts at its +0x1c, which the mod checks.
- **No false new messages:** translations are added right after a chat check in the same frame, then the ring header is read again as the new baseline, so the added lines never count as new (no sound, no translation of a translation).
- **The request:** `curl.exe -sS -m 8 --max-filesize 131072 -G --data-urlencode q@- -w "\n@@ %{http_code}" "https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=auto&tl=<target>"`, started with `CreateProcessW` (`CREATE_NO_WINDOW`, a handle list with only curl's own pipe ends, System32 as its folder). The line goes in on curl's standard input (`q@-`), never on the command line; the reply comes back through a pipe polled every frame with `PeekNamedPipe` (the game never waits). One curl at a time, up to 8 lines queued, a curl still running after 12 s is ended. Target = the game's Text Language mapped to Google's codes (pt-BR > pt, pt > pt-PT, zh-Hans > zh-CN, zh-Hant > zh-TW, es-419 > es). The reply is `[[[part, original, ...], ...], null, "<detected>", ...]`; a line already in the target language (same base language; Chinese scripts differ) or translated to itself is not shown.
- **Measured outside the game (real kernel32, curl 8.21 on Windows 11):** `CreateProcessW` takes 9 ms the first time and about 2 ms after (the only cost on the game's frame); replies took 300-1150 ms. es, zh-CN and pt were detected correctly.
- **Limits:** curl.exe ships with Windows 10 1803 and later; Proton/Wine has none (translation stays off, the status says why). The endpoint is unofficial (no key, may rate-limit or change). Only players with the mod see translations.

## Recon 3-1 (live, 2026-10-06)

Test build `Better-Chat-3-recon-1`: Translate Chat (off by default), Show In Chat (off: translations only in BetterChat.log) and Translate My Messages (to try it alone). This build logs each line's text and translation to BetterChat.log; the release should log neither.

- Translations work in game: Spanish and German lines (your own, via Translate My Messages) were detected and translated in 626-836 ms; starting curl took 6-14 ms of the frame.
- The first line got HTTP 500 from the endpoint (its text was not logged on failure). Not reproduced offline: 15 requests in a row got 200, and invalid UTF-8 gets 200 too (misdetected).
- Show In Chat was on only for that failed line and was turned off before the next ones, so add-line was never called: showing is still untested.

## Recon 3-2 (live, 2026-10-06)

Test build `Better-Chat-3-recon-2`: a 5xx reply or a curl failure (network) is retried once after 1 s (not a 429 or a timeout); failures log the line's text; a breadcrumb line is logged before each add-line call.

- **Showing works:** add-line called from the Lua update added "[PT] this is a message in Portuguese" and "[EU] no" to the chat under the sender; the added lines were never seen as new lines (the ring slots they took are absent from the "Line" entries). No crash, no 500 this time.
- **Short lines are misdetected:** "ez" came back as Basque ("no"). Google's detection confidence does not separate them (Portuguese sentence 0.57, "ez" 0.61, "o7" Arabic 1.0). Rule since 3-3: an ASCII-only line with fewer than 4 letters is not sent ("gg", "ez", "o7", "ok", "lol"); a line with any other script always is.

## Paste (offline, 2026-10-06)

Request: Ctrl+V in the chat (the game has no paste). Decompiles: `_research/chat/paste/` (`textfield.c`, `text_input.c`).

- **Input open:** the chat widget (HUD + chat_hud) byte +0x139b8 is set while the text input is open: the chat update `0x185fd10` runs the text field (widget + 0x1398, text at +0x16d4 = field + 0x33c) only then, and closes it through `0x185f500(widget, 0)`. Signature `chat_input` at `0x18608d0` (a widget function that starts by testing the byte; 34 bytes, the offset read from it).
- **Where typed text comes from:** the text field update `0x18f2dc0` calls `0x12fd9b0(?, text, size)`, which walks the input devices (type 3 = keyboard) and reads that frame's keystrokes, an array of Unicode code points (the engine's `Keyboard.keystrokes`, filled from the window's WM_CHAR). Code points >= 0x20 are appended as UTF-8 within the size; 8 (backspace), 10/13 (enter), 27 (escape) and 9 (tab) end the frame's processing with their own result. The field then cuts to its character limit (+0xa84 - 1). Ctrl+V gives 0x16, which is ignored: no paste in the game. Separately, game mode +0xac564 == 1 takes text from the engine (`[engine + 0x10] + 0x650`): Steam's gamepad text input.
- **Design:** on Ctrl+V (`GetAsyncKeyState`, an edge on V with Ctrl held) while the input is open and the foreground window belongs to this process, the clipboard's CF_UNICODETEXT is posted to that window as WM_CHAR, 16 per frame, at most 256 characters. Line breaks and tabs become one space, other control characters and surrogates (emoji: WM_CHAR would deliver halves) are left out. The game's own typing path keeps its limit and filters; no game memory is written. The paste stops if the chat closes.
- **Checked outside the game:** the real clipboard read (LuaJIT, real user32) turned "olá mundo\r\nsegunda linha\tfim 😀 ok" into "olá mundo segunda linha fim ok".

## Recon 3-3 (live, 2026-10-06)

Test build `Better-Chat-3-recon-3`: Paste (Ctrl+V) through posted WM_CHAR, on by default; translation skips short ASCII lines.

- **Paste failed:** every Ctrl+V was caught and its characters posted to the game window (`Paste: 16 characters`, ten times), but nothing reached the chat. The engine does not build its keystrokes from posted WM_CHAR (it may read the keyboard another way; helldivers2.exe is packed, not analysed).
- **The target language was wrong for the user:** the game's Text Language is English (`us`) while the player writes Portuguese, so "translate into the Text Language" turned their own Portuguese into English. On this PC Windows' display language and Steam are English too; only Windows' regional format is pt-BR (home location Brazil; user languages en-US, pt-BR).

## Paste through the text setter (offline, 2026-10-06)

Decompile: `_research/chat/paste/set_text.c`.

- `0x143dd60(text widget, text)` is the game's generic text widget setter (about 70 callers): it refuses text of 0x324 bytes or more, compares with the widget's text at +0x11c, copies (0x325) and refreshes the widget (`0x143de70`). The chat's text field calls it on its text widget (field + 0x220, whose +0x11c is the field's text at +0x33c) for Steam's text input. `0x18f39c0(field)` only scrolls the text so its end shows; the field's update calls it every frame.
- **Design:** on Ctrl+V with the input open and the game window in front: the field's current text + the clipboard's (cleaned, UTF-8), cut to the field's character limit (+0xa84 minus 1) and under 0x324 bytes on character boundaries, through the setter. The next field update keeps it (no keystrokes) and applies its own limit again. No game memory is written by the mod.
- Signatures: `chat_field` (the chat update's call to the field update: field = widget + 0x1398), `field_text` (the Steam text input branch: +0xa84, +0x220 and the call to the setter, which must be `set_text`) and `set_text` (0x324, +0x11c). The branch must lie inside the field update the chat calls.

## Translate To (2026-10-06)

A choice: Automatic (default: the language of Windows' regional format, `GetUserDefaultLocaleName`; else Windows' display language; else the game's), Game Language, or one of 13 languages (the game's, Spanish once: Google has one). Tags map to Google codes: pt-BR and pt > pt, other pt-* > pt-PT, zh Hant/TW/HK/MO > zh-TW, other zh > zh-CN, else the language subtag. A line already in the target language (same base language, Chinese scripts apart) is not shown, so Brazilian Portuguese is never translated to European Portuguese. Read live on this PC with the real API: regional format pt-BR, display language en-US.

## Recon 3-4 (live, 2026-10-06)

Test build `Better-Chat-3-recon-4`: paste through the game's text setter; Translate To.

- **Paste works** through the setter (confirmed by the user).
- **Translation works with another player** (sender `b0ef1d999fb9b08a`): his Portuguese lines were shown as Spanish, French and English as Translate To changed; his English line was not shown with Translate To = English; Automatic gave pt and translated "I LOVE YOU VERY MUCH" to Portuguese. Latency 275-1630 ms, curl start about 5 ms (12-14 ms the first times).
- The original line stays and the translation is added below it (the user wanted it so: "important to leave the original message in").

## V3

- Paste (Ctrl+V, on by default) through the game's text setter; Translate Chat (off by default) with Translate To (Automatic = Windows' regional format) and Translate My Messages (kept as a setting so a player can try translation alone). Show In Chat was a test option and is gone: translations are always added to the chat.
- The log never holds a message's text, its translation or the endpoint's reply (only curl's own error message when curl fails); the paste line logs only a byte count.
- Public docs (README, Nexus, CHANGELOG) mark translation as highly experimental (the user's wording, an exception to the no-experimental rule) and state that only the player sees translations, what is sent and to whom.

## Louder alert sounds (offline, 2026-10-06)

Request: instead of a volume setting, offer game sounds that are louder by themselves. Tools: `research/sound_ids.py` (ids the code passes to the UI sound function and to post_audio: 281 and 37) and `research/sound_survey.py` (needs HD2ReAudio's core, hd2-audio-modder's v154 parser and vgmstream). Outputs in `_research/chat/sounds/` (`survey/survey.tsv` and `.json`, `names_cracked.txt`, `listen/*.wav`).

- **The sound map is game data, not runtime state.** `0x1255800` loads the resource of type `0xe3f2851035957af5`, name `0xb9ee36888ef19818` (`[engine + 0x10] + 0x3f8`): u32 capacity (65536), then capacity x (game id, Wwise event id) with 0 for an empty slot, then a second table of the same shape. 20,848 sounds. It reproduces every id pair read live in recon 2-1. Extract it with `go run ./cmd/res_dump <data> 0xe3f2851035957af5 <out>` (res_dump takes a raw type hash now).
- **A game sound id is a name hash.** id = the upper 32 bits of MurmurHash64A (seed 0) of the Wwise event name; the Wwise id is FNV-1 of the same name. Checked on 164 known names (`music_mission_leave` > 0xc26f4705 > 137483901). So an id is stable across game updates while the event keeps its name, and a guessed name can be verified against 64 bits. A dictionary search (words joined with `_` after `ui_`, `hud_`, `menu_`) named 127 UI events: `ui_generic_tab` (Menu Tab), `ui_generic_select` (Menu Subtab), `ui_generic_popup_confirm`, `ui_generic_back`, `hud_wheel_social_open`, `hud_mission_complete_appear`, `hud_death_notification_appear`... The join and leave notices and the two loudest sounds stayed unnamed.
- **Banks:** UI sounds are in `content/audio/ui_ship` (616 events) and `content/audio/ui_mission` (330); 100 events are in both, which is what an alert needs to play on the ship and in missions. `game_init` holds states and parameters, no sounds. The chat's own open, close and send events (0x74ef3f93, 0x5d5ed59c, 0xe1ba68c0) exist with no actions, which is why Message Sent was mute in recon 1.
- **Each UI event plays two sounds:** the audio (Wwise Vorbis) and a generated source (plugin 0x830402, most likely controller haptics).
- **Loudness score** = the loudest 100 ms of the decoded audio (RMS, dBFS) + the volume property (id 5 in these banks, dB) of the sound and its parents. Bus volumes are not included (two buses are in use: 4061956780 for menu sounds, 2438906104 for HUD sounds). The current choices: Player Joined -33.8, Option Click -35.1, Menu Tab -35.4, Player Left -40.4, Menu Subtab -43.6. Positioning does not matter: the join notice is a 3D sound and plays fine on the source the UI sound function makes.
- **Louder sounds in both banks (3 s at most):** 0xa1af099e -20.0 (2.34 s; 35 ids share its audio, name unknown), 0xd8fc9d33 -24.3 (1.25 s, name unknown), `ui_generic_popup_confirm` 0x7a69c309 -28.0 (1.38 s), `ui_generic_back` 0x96c8c848 -28.2 (1.5 s), `hud_wheel_social_open` 0x22200946 -28.3 (0.8 s), `ui_generic_popup_open` 0xd2758677 -29.4. Louder still but in one bank only: `hud_death_notification_appear` -15.8 (mission, 3.9 s), `ui_loadout_menu_ready_player` -21.7 (ship, 3 s), `hud_mission_complete_appear` -20.9 (mission, 6 s).

## Clean Chat (offline, 2026-10-06): not released

Request: only player-sent messages in the chat. Decompile: `_research/chat/clean/notices.c`. **The design built in 4-recon-1 and 4-recon-2 wrote game code and was detected by GameGuard (see Recon 4-2 result); it is gone since 4-recon-3. Never write game.dll's code.**

- **Every line the chat shows goes through `0x185f470(chat widget, feed entry, seconds)`:** it writes the next of the widget's lines and shows the chat for that long. The entry comes from the HUD's feed log (hud + 0x4f7080: a ring of 64 entries of 0x4b4 bytes, index +0x12d00, count +0x12d04; an entry starts with the id of its text format, 0x1c12037f for a chat line).
- **15 calls in build 25480438.** One is the chat notice's (`0x12f3022`, the last instruction of the `chat_notice` signature): a player's line, and the translations this mod adds through add-line. The other 14 are the game's own notices: `0x12f21cc`, `0x12f23f9` (inside the player joined notice `0x12f21e0`), `0x12f268f`, `0x12f2a3f`, `0x12f2ca6`, `0x12f2d97`, `0x12f2f3a`, `0x12f5c57` and six in network message handlers (`0x607e8c`, `0xb600f4`, `0xb8405b`, `0xb92780`, `0xb9958e`, `0x1088454`). Which notice each one is was not worked out; none carries a player's text.
- **The rejected design:** each of the 14 calls replaced by a 5-byte no-op through `WriteProcessMemory` while the option was on. It worked offline and applied cleanly in game (14 of 14), and the game was closed by GameGuard or crashed within a minute each time.
- **The chat widget** (hud + 0x14498): 64 line widgets of 0x3d8 bytes from +0x4390, next slot at +0x13990, line count at +0x139c0 (stops at 64), shown height +0x139c4, show timer +0x139c8 (seconds), input open +0x139b8, hidden +0x139ba. A line: flags +0 (0x10 visible), text widget +0x110, a state byte +0x3c8 (the update clears it when it hides lines), target position +0x3cc, move pending +0x3d4. `0x185f470` = set the line (`0x1860b00`: the text widget gets the entry's format id, name, colours and text) + `0x185f170` (next slot + 1, count + 1, then every line from the newest is placed at the summed height of the newer ones and made visible) + timer = max(timer, seconds) + un-hide (`+0x139ba` cleared, fade in). The chat update `0x185fd10` follows the player's chat visibility setting `[game state + 0xac53c]` (0 always shown, 1 shown until the timer runs out, 3 hidden) and hides through `0x185f130`.
- **A way without code writes (idea, not built):** remove a notice's line after the game added it. Each frame read the next slot and count; for a new line that is not a chat line, put the next slot and count back by two (two data writes in the HUD object, which is heap memory), call `0x185f170` to lay the lines out again, hide the removed line's widget with the game's widget visibility setter, restore the timer and call `0x185f130` if the chat was hidden. Open: where the line's text widget keeps the format id (to tell a notice from a player's line), whether Lua's update runs before the frame is drawn (else the line shows for one frame), and several lines added in one frame. A new build must use a new option id: the user's Mod Options Menu values still hold `alomare.better_chat.clean = true`. The texts written for the option are in `research/clean_chat_texts.tsv`.

## Recon 4-1 (test build, 2026-10-06)

Test build `Better-Chat-4-recon-1`: Clean Chat by code patches (off by default; removed in 4-recon-3); the Paste setting is gone (paste is always on; a saved value for it in Mod Options Menu is ignored); five new sound choices given by their ids: Menu Confirm, Menu Back, and three with test names, Social Wheel, Loud A (0xa1af099e) and Loud B (0xd8fc9d33). To check live: Clean Chat hides the join and leave lines and keeps players' lines and translations, both ways without a restart; each new sound plays on the ship and in a mission and is louder; what Loud A and Loud B are, to name them.

## Recon 4-1 result (live, 2026-10-06)

- Every new sound played from the menu on the ship (the log shows each preview). The user named the three test choices: Loud A (0xa1af099e) is Item Purchase, Loud B (0xd8fc9d33) is Confirmation Dialog, Social Wheel (0x22200946) is Action Wheel.
- Clean Chat was turned on (14 of 14 notice calls) and the game crashed seconds later, before any chat line was seen. The dump (`%APPDATA%\Arrowhead\Helldivers2\dumps`) is an access violation at `helldivers2.exe+0x626296` on a rendering thread: a read of `[rax + rcx*8 + 4]` with a bad index, the stack holding only helldivers2.exe, d3d11.dll and the AMD driver. The 11 older dumps kept there, from 2026-09-29 on (Better Chat's first build is of 2026-10-06), have the same address and the same kind of stack. I took that as proof that Clean Chat was not involved; Recon 4-2 says otherwise.

## Recon 4-2 (test build, 2026-10-06)

Test build `Better-Chat-4-recon-2`: the three sounds under their names, translated; nothing else changed (Clean Chat still by code patches).

## Recon 4-2 result (live, 2026-10-06): GameGuard

Three sessions in three minutes (GameGuard's own logs in `bin/GameGuard` are dated 19:42:02, 19:43:39 and 19:44:42), Clean Chat on from the saved setting, so the calls were patched 0.2 s after the mod loaded:

1. Better Chat and a few other mods: GameGuard's "suspicious program detected", the game closed, about a minute after launch.
2. Better Chat off: no problem in 1 to 2 minutes.
3. As 1: a crash. The log shows Clean Chat on at t14.8, off at t47.2 and on again at t48.0 (19:44:33.9, the user changing the option); the escape menu closed at 19:44:34.6 and the game was gone by 19:44:38. The dump is the same fault at `helldivers2.exe+0x626296`.

- **Writing game.dll's code is detected.** Clean Chat was the only part of the mod that wrote game memory at all, and the only thing new since V3 besides sound ids and a removed setting. It matches what the other runtimes say: HD2Runtime "patches no game code: no detours, no `.text` writes (the Bingus community convention, and the game ships GameGuard)", and Mod Bindings Menu writes only game.dll's read-write data section. The hd2-lua-mod skill only warns about reading from another process; this is the missing half.
- **The crash:** both crashes of this day came seconds after a Clean Chat write, so the patches are the likely trigger of those two. The same fault is in 11 dumps from before Better Chat existed, so it has another trigger as well; which one is not known (the stack never holds mod code). If it comes back without code patches, look at what the two logged cases share besides the patch: the escape menu's MODS tab had just been used.
- Nothing lasts beyond the session: the patches were in memory only.

## Recon 4-3 (test build, 2026-10-06)

Test build `Better-Chat-4-recon-3`: Clean Chat removed (the option, the search of the game's code and every write; the script has no WriteProcessMemory any more, which a test checks). Kept from 4-recon-2: the five louder sounds and paste without a setting. To check live: no GameGuard message and no crash in a normal session with the same mods.

## Recon 4-3 result (live, 2026-10-06)

The user confirmed that Clean Chat was the cause, and dropped it: it stays out of the mod.

## V4

- Five louder New Message Sound choices given by their ids (Menu Confirm, Menu Back, Action Wheel, Item Purchase, Confirmation Dialog), after Option Click so the earlier choices keep their numbers. The Paste setting is gone: paste is always on, and a value saved for it in Mod Options Menu is ignored.
- No Clean Chat. The mod writes no game memory.

