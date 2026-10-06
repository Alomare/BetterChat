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
