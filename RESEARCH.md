# Better Chat: how it works in the game's code

Better Chat watches the game's text chat for new lines and plays one of the game's own UI sounds when another player's line arrives, scales the chat box, adds Ctrl+V paste to the chat's text input, can add machine translations of other players' lines to the local chat, and can send the player's own lines translated through the chat's own send. Everything native is in `game.dll`. All addresses below are `game.dll` RVAs for Steam build 25480438; the mod does not rely on them: it finds each one with the code signatures in `research/signatures.py` (tried at the known address first, else searched in `game.dll`'s executable sections, matching exactly once) and reads globals and structure offsets from the matched instructions, so it survives updates that only move code. `[x]` means the pointer stored at RVA `x`; `[x] + y` means that pointer plus `y`.

The mod reads game memory only (`ReadProcessMemory` on its own process, which fails instead of crashing on a bad address) and changes the game only by calling the game's own functions. It writes no game memory and never patches code (see [Dead ends](#dead-ends)).

## The chat object and its history

- **Chat object:** the network context `[0x347cef0]` + 0xc418. Its byte +0 is "text chat enabled" (add-line returns at once when it is 0). The local player's peer id (u64) is at context + 0xb398.
- **History ring:** 64 lines of 0x228 bytes from chat + 0xb90. First index at chat + 0x9590, line count at chat + 0x9594 (u32 each, adjacent, so one 8-byte read gets both). The count stops at 64; after that each new line advances the first index (mod 64). Both are zeroed by the reset `0x1097010`.
- **A line:** +0 time (u64), +8 sender peer id (u64), +0x10 UTF-8 text (0x201 bytes, NUL-terminated), +0x211 friend, +0x212 / +0x213 filter state, +0x214 / +0x215 display flags, +0x220 platform (int).
- **Detecting new lines (live-proven):** read the header, count new lines as (count change) + (first index change mod 64); a lower count or another context pointer is a new session or a cleared history and only sets a new baseline. Compare each new line's sender with the local peer id to tell your own lines from others'. Better Chat does this every 200 ms of frame time.
- Lines from a muted or blocked player never reach the ring (add-line drops them), so a reader of the ring never sees them.

## Add-line, the send path and the chat notice

- **Add-line `0x10979c0(chat, sender, text)`:** every chat line goes through it. Callers: the chat box's send `0x1097560` (your own lines, sender = the local peer id) and the two RPC receive handlers `0xb954b0` and `0xbb6210` (+ `0x1097c90`). It drops a line from a sender the chat doesn't know (no longer in the session) or one muted or blocked (`0x13e5220`), hands another player's text to the platform filter (see below), copies the text with a bounded copy into the line's 0x201 bytes, and ends with the HUD notice. Add-line itself sends nothing over the network: the network send is in `0x1097560`.
- **Adding a local-only line (live-proven):** calling add-line from Lua with another player's peer id adds a line to your chat under that player's name, visible only on your machine. Keep the text under 0x201 bytes (Better Chat cuts at 0x1f0 on a UTF-8 character boundary). The added line takes a ring slot like any other, so re-read the ring header afterwards and take it as the new baseline, or your own reader will count it as a new message.
- **The chat's send `0x1097560(chat, param_2, text)`:** `param_2` is never read (the chat box passes the index of the first non-space character). It cuts the text at 0x200 bytes on a UTF-8 boundary, returns at once when the chat's byte +0 is 0, runs a check `0x174fa80(text, -1)` (nothing is sent when it fails; its meaning was not worked out), sends the text to every peer of the context's list (count at context + 0x16390, 0x20-byte entries from +0x16398) except muted ones (`0x13e5220`) and the local peer, then adds it to the local chat through add-line (the call at `0x10977ee`, sender = context + 0xb398). A text of exactly "f" or "F" also raises event 0x4790a9e1 (paying respects).
- **The chat box (`0x185fd10`)** calls the send when the text field's update reports Enter and the field holds a non-space character, then plays 0xe1ba68c0 (an empty event) and closes the input (`0x185f500(widget, 0)`); an empty field only closes the input.
- **Sending a line from Lua (live-proven, solo):** calling the send with the chat and a text adds it to your chat as your own line, like a typed one; it was not yet checked from a squadmate's side. Re-read the ring header afterwards, as for add-line.
- **Taking a typed line before the game sends it (live-proven):** the Lua update runs before the game's chat update in the frame Enter arrives. Reading the field's text and Enter's key state each frame while the input is open, then emptying the field through the text setter on Enter's press, leaves the game an empty field: it sends nothing and closes the input. Every try took the text first. A mod that does this should still detect the opposite order (the field already empty on Enter after holding text, or the taken text arriving in the ring as your own line) and then not send its own copy.
- **HUD notice `0x12f2f60(_, sender, text)`:** formats "<name>: text" (text format id 0x1c12037f) into the chat widget through `0x185f470`, then, for anyone but the local player, calls the UI sound function with id 0, which plays nothing: the game has an empty "message received" sound slot.

## Text filter

- The platform object `[0x3326e48]` has a byte at +0x2494, set at platform init (`0x13e7d50`) from a platform service call. When it is set, add-line passes another player's text to the platform filter (`[[engine + 0x148] + 0x58] + 0x10`, mode 2, with `engine` the engine function table below); when 0, the text is copied as typed. Your own lines are never filtered. The byte is also read where player names (0x80-byte strings) are copied, likely the lobby members (`0x1095620`), and by two filter callbacks.
- On Steam the byte is 1, yet swear words between two Steam players arrive unfiltered: the platform filter leaves PC text alone. Lines from console (PSN) players were not checked.

## UI sounds

- **Game mode:** `[0x3326340]` + 0xac21c, 3 on the ship, 4 in a mission.
- **UI sound function `0x1327f50(unused, id)`:** plays a game sound id on a new sound source of its own (no position). It is three engine calls: `source = [engine + 0x288](wwise_world)`, `event = 0x12556e0(id)` (game id to Wwise event id), `[engine + 0x338](wwise_world, event, source, 0)`, where `engine` = `[0x3326318]` (the engine's script function table, helldivers2.exe functions; game.dll references it about 2,100 times) and `wwise_world` = `[[0x3326340] + 0x10f8]`. A sibling `0x4dcbc0` does the same through `+0x1e8`. Calling it from Lua through FFI is safe and plays the sound for the local player only.
- **A game sound id is a name hash:** the id is the upper 32 bits of MurmurHash64A (seed 0) of the Wwise event name; the Wwise event id is FNV-1 of the same name (checked on 164 known names, e.g. `music_mission_leave` > 0xc26f4705 > 137483901). An id therefore stays the same across game updates as long as the event keeps its name, and a guessed name can be verified against 64 bits.
- **The sound map is game data:** `0x1255800` loads the resource of type `0xe3f2851035957af5`, name `0xb9ee36888ef19818` (through `[engine + 0x10] + 0x3f8`): a u32 capacity (65536), then capacity x (game id, Wwise event id) pairs with 0 for an empty slot, then a second table of the same shape. It holds 20,848 sounds. FileDiver can extract it by its raw type hash.
- **Banks:** UI sounds are in `content/audio/ui_ship` (616 events) and `content/audio/ui_mission` (330); 100 events are in both, which is what a sound needs to play both on the ship and in missions. `game_init` holds states and parameters, no sounds. Each UI event plays two things: the audio and a generated source (plugin 0x830402, most likely controller haptics).
- **The chat's own sounds are empty:** open 0x74ef3f93, close 0x5d5ed59c and send 0xe1ba68c0 exist with no actions, so posting them plays nothing.
- **Menu sounds:** the game's standard button sound record (init `0x14a47d0`) holds hover at +4 (0x65e34ad8) and click at +8 (0x468c8e58); many menus copy it into their buttons (e.g. `0x1499240`). The menu tab bar (`0x17aac50` sets its labels; up to 8 tabs of 0xd48 bytes) is made of buttons of class `0x17af630` (states 0-9 at +0xd20) whose init `0x17ae3xx` sets hover +0xd40 = 0x78e15850 and click +0xd44 = 0xadd37058 (state 4 plays +0xd40, states 6 and 8 play +0xd44). An option row's arrow (`0x17fdd30`, `0x17fde75`) plays 0x144418d5 when the value changes and 0x3e8c63db when it can't. The OPTIONS page plays 0x468c8e58 on APPLY. Menu open and close are 0x400d9983 / 0x702f7ffb plus mix states (`0x1455840`, `0x1459140`).
- **HUD feed notices:** "player joined" `0x12f21e0` plays 0xda653421 on the ship and 0x82250982 in missions; "player left" `0x12f26b0` plays 0xc386a64a / 0x03cf15e0.

The sounds Better Chat offers, all live-proven to play through `0x1327f50`:

| Choice | Game id | Wwise event id | Name or source | Bank | Loudness score |
|---|---|---|---|---|---|
| Player Joined | ship 0xda653421, mission 0x82250982 | 2625604776 / 147058876 | read from the "player joined" notice | both | -33.8 |
| Player Left | ship 0xc386a64a, mission 0x03cf15e0 | 3285929117 / 2669315291 | read from the "player left" notice | both | -40.4 |
| Menu Tab | 0xadd37058 | 3782250789 | `ui_generic_tab`, read from the tab button init | both | -35.4 |
| Menu Subtab | 0x468c8e58 | 2156104120 | `ui_generic_select`, read from the button sound record | both | -43.6 |
| Option Click | 0x144418d5 | 1540929694 | read from the option row's arrow | both | -35.1 |
| Menu Confirm | 0x7a69c309 | | `ui_generic_popup_confirm` | both | -28.0 |
| Menu Back | 0x96c8c848 | | `ui_generic_back` | both | -28.2 |
| Action Wheel | 0x22200946 | | `hud_wheel_social_open` | both | -28.3 |
| Item Purchase | 0xa1af099e | | name unknown (35 ids share its audio) | both | -20.0 |
| Confirmation Dialog | 0xd8fc9d33 | | name unknown | both | -24.3 |
| Reinforce Request | 0x4a300afb | 0x36b4a8db | name unknown | `ui_mission` only | |
| Countdown | 0x9da28dab | 0xdf38444b | name unknown | `ui_mission` only | |

- **Loudness score** = the loudest 100 ms of the decoded audio (RMS, dBFS) plus the volume property (id 5 in these banks, dB) of the sound and its parents; bus volumes are not included (menu sounds use bus 4061956780, HUD sounds 2438906104). Louder sounds exist in one bank only: `hud_death_notification_appear` -15.8 (mission, 3.9 s), `hud_mission_complete_appear` -20.9 (mission, 6 s), `ui_loadout_menu_ready_player` -21.7 (ship, 3 s). Positioning does not matter: the join notice is a 3D sound and plays fine on the unpositioned source the UI sound function makes.
- **Reinforce Request** is a continuous sequence (loop 1, no transition) of a Wwise Silence source (plugin 0x00650002, no parameters, so Wwise's default of 1 s) and then one random take of three (1.68 s), plus a haptics source: it starts 1 s after it is posted, as in the game. No event plays the takes without the silence. Game code posts it through the UI sound function at `0x60b2c6` and `0xb83a85` (0xba33ce36 maps to the same event); with a flag bit set it posts 0xda1fb33b instead. The event `hud_spectator_request_reinforce` (0x3b3d2f51) is empty.
- **Countdown** is a sequence with one child, a random take of six (1.5 s each). The game plays it once when a player leaves the mission area and stops it with 0xdf59b412 or 0x4cac138d when they come back.

## The engine function table and Wwise

Entries of the engine table `[0x3326318]` that concern Wwise, named from the game's native replacements of the Wwise flow callbacks (`0xfc5550` replaces `WwiseFlowCallbacks.wwise_trigger_event`, `wwise_make_auto_source` and `wwise_make_manual_source` with native code: `0xfc4c50`, `0xfc51d0`) and from other callers (offline reading):

| Offset | Function |
|---|---|
| +0 | the invalid source id |
| +0x58 | `wwise_world(world)` |
| +0x288 | make a source `(ww)` |
| +0x298 | make a source at a pose `(ww, matrix, debug name)` |
| +0x2a0 | make a source on a unit `(ww, unit, node)` |
| +0x2a8 | a unit's existing source (0xffffffff = none) |
| +0x2e0 | `(ww, source, seconds)` |
| +0x2e8 / +0x2f0 | set manual `(ww, source, bool)` / is manual |
| +0x338 | trigger event `(ww, event id, source, 0)`, returns the playing id |
| +0x380 | source parameter (RTPC) `(ww, source, parameter id, value)` |
| +0x3a0 / +0x3a8 | environment (aux bus) by name / by id `(ww, bus, value)` |
| +0x458 | `(ww, source, bool, float)`, called with (1, 1.0) after every positioned source; meaning unknown |
| +0xa0 / +0x1b8 / +0x1c0 | global parameters by name / by id |

- **A per-source level exists only in the Lua API:** the game's own `core/wwise/lua/wwise_flow_callbacks` uses `stingray.Wwise.wwise_world(world)` and `stingray.WwiseWorld.set_dry_environment_for_source(wwise_world, source_id, value)`. In Stingray the dry level is Wwise's `SetGameObjectOutputBusVolume` (a linear gain on that game object's output). game.dll never calls that table entry, so its offset is not known from game.dll.
- **Lua cannot post these sounds itself:** `WwiseWorld.trigger_event` takes event names, and the game passes only ids. Mixing the two (native make source and post, Lua for the level in between) needs Lua's Wwise world matched to the native one: `Wwise.wwise_world(world)` returns a full userdata (a Lua heap box, one per world), so `string.format('%p', ...)` gives the box's address, not the native Wwise world, and the match fails. Reading the userdata's payload and comparing it with `[[0x3326340] + 0x10f8]` was not tried. Calling `Application.main_world`, `Application.worlds` and `Wwise.wwise_world` on all 12 worlds on the ship is safe.
- Lua API present in game (live): `Wwise`: duration_type, has_event, load_bank, max_attenuation, max_duration, min_duration, position_type, set_language, set_panning_rule, set_state, unload_bank, wwise_world. `WwiseWorld`: add_default_listeners, add_soundscape_listener, add_soundscape_unit_source, add_source_listeners, destroy_manual_source, enabled, get_playing_elapsed, has_source, is_playing, make_auto_source, make_manual_source, pause_all, pause_event, post_trigger, remove_default_listeners, remove_soundscape_listener, remove_soundscape_source, remove_source_listeners, reset_aux_environment, reset_environment_for_source, resume_all, resume_event, set_dry_environment, set_dry_environment_for_source, set_enabled, set_environment, set_environment_for_source, set_global_parameter, set_listener, set_source_lifetime, set_source_parameter, set_source_pose, set_source_position, set_switch, stop_all, stop_audio_input_sound, stop_event, trigger_audio_input_event, trigger_audio_input_sound, trigger_event, unlink_source.
- The player's volume settings (`audio_volume`, `dialogue_volume`, `music_volume`, `sfx_volume`, `voice_chat_volume`, `tts_volume`: floats at the start of the settings object, read by `0x102c9c0`) are global; there is no per-sound volume.

## The chat widget

The chat's HUD widget is the HUD `[0x346d538]` + 0x14498; the HUD's +0x24e335 byte is its active flag. Its update is `0x185fd10`.

- **Layout fields** (any widget): position +4/+8, size +0xc/+0x10, scale +0x14/+0x18. The widget scale setter `0x1447ed0(widget, &vec2)` compares with +0x14/+0x18. The game never scales the chat (`0x1860910`, set_scale(s, s), and `0x1860930`, store +0x139a0, have no callers), but scaling it with `0x1447ed0` works and scales its text (live-proven). A new HUD layout (after loading) resets the scale, and the scale is 0 until the widget is laid out, so re-check it periodically and leave a scale-0 widget alone.
- **Position:** when the docked state (+0x139be) changes, the update fades the chat out, then applies position, anchor and pivot: docked (0, -20), (0.5, 1), ...; undocked its own fields +0x139a0 (position; (-36, 81) read live), +0x139a8 (anchor), +0x139b0 (pivot), through set_position `0x14476a0`, set_anchor `0x144f160` and set_pivot. In missions (mode 4, `[0x346d530]` + 0x190c != 6) it sets the position every frame to the field plus (0, something * 433), and the minimap displaces the chat.
- **Height:** the line stack plus 66, clamped to 40..185 by read-only data constants; width 400. More visible lines would need those constants changed.
- **Lines:** 64 line widgets of 0x3d8 bytes from +0x4390, next slot at +0x13990, line count at +0x139c0 (stops at 64), shown height +0x139c4, show timer +0x139c8 (seconds), text input open +0x139b8, hidden +0x139ba. A line: flags +0 (0x10 visible), text widget +0x110, a state byte +0x3c8 (cleared when lines are hidden), target position +0x3cc, move pending +0x3d4.
- **`0x185f470(chat widget, feed entry, seconds)`** shows every line the chat shows: it sets the next line (`0x1860b00`: the text widget gets the entry's format id, name, colours and text), calls `0x185f170` (next slot + 1, count + 1, then lays out every line from the newest at the summed height of the newer ones and makes it visible), sets timer = max(timer, seconds) and un-hides the chat (clears +0x139ba, fades in). The update follows the player's chat visibility setting `[0x3326340]` + 0xac53c (0 always shown, 1 shown until the timer runs out, 3 hidden) and hides through `0x185f130`.
- **The HUD feed log** (the entries passed to `0x185f470`) is HUD + 0x4f7080: a ring of 64 entries of 0x4b4 bytes, index at +0x12d00, count at +0x12d04; an entry starts with the id of its text format (0x1c12037f for a chat line).
- **15 calls to `0x185f470` in build 25480438:** one is the chat notice's (`0x12f3022`, a player's line); the other 14 are the game's own notices: `0x12f21cc`, `0x12f23f9` (inside the player joined notice `0x12f21e0`), `0x12f268f`, `0x12f2a3f`, `0x12f2ca6`, `0x12f2d97`, `0x12f2f3a`, `0x12f5c57`, and six in network message handlers (`0x607e8c`, `0xb600f4`, `0xb8405b`, `0xb92780`, `0xb9958e`, `0x1088454`). Which notice each is was not worked out; none carries a player's text.

## The chat's text input and paste

- **Input open:** the chat widget's byte +0x139b8 is set while the text input is open. The update runs the text field (widget + 0x1398, its text at +0x16d4 = field + 0x33c) only then, and closes it through `0x185f500(widget, 0)`. `0x18608d0` is a widget function that starts by testing that byte.
- **Typed text:** the text field update `0x18f2dc0` calls `0x12fd9b0(?, text, size)`, which walks the input devices (type 3 = keyboard) and reads that frame's keystrokes, an array of Unicode code points (the engine's `Keyboard.keystrokes`). Code points >= 0x20 are appended as UTF-8 within the size; 8 (backspace), 10/13 (enter), 27 (escape) and 9 (tab) end the frame's processing with their own result. The field then cuts to its character limit (+0xa84, minus 1). Ctrl+V gives 0x16, which is ignored: the game has no paste. When game state + 0xac564 == 1 the field takes text from the engine instead (`[engine + 0x10] + 0x650`): Steam's gamepad text input.
- **Text widget setter `0x143dd60(text widget, text)`** (about 70 callers): refuses text of 0x324 bytes or more, compares with the widget's text at +0x11c, copies (0x325 bytes) and refreshes the widget (`0x143de70`). The chat field calls it on its text widget (field + 0x220, whose +0x11c is the field's text at +0x33c) for Steam's text input. `0x18f39c0(field)` only scrolls the text so its end shows.
- **Paste that works (live-proven):** on Ctrl+V with the input open and the game window in front, set the field's current text plus the clipboard's text (UTF-8, cut to the field's character limit and under 0x324 bytes on character boundaries) through the setter. The field's next update keeps it and applies its own limit again. Characters outside the Basic Multilingual Plane (emoji) must be left out.

## Starting a process from the game (translation)

Better Chat's translation runs Windows' `curl.exe` (Windows 10 1803 and later; Proton/Wine has none) against Google's unofficial keyless endpoints or a custom service (next section). Findings that apply to any mod that starts a process:

- **Start it without blocking the game:** `CreateProcessW` with `CREATE_NO_WINDOW`, pipes for standard input and output, this process's pipe ends made non-inheritable and a `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` holding only the child's two ends, System32 as its folder. Write the input once (keep it under the pipe's buffer, 0x4000 here with configs of at most 0x3f00 bytes, so the write never waits), then poll the output pipe each frame with `PeekNamedPipe` and end a process that runs too long. The game's frame then pays only for `CreateProcessW`: about 5-6 ms in game, about 2 ms outside it.
- **Keep addresses and changing text off the child's command line.** In the game process, the first start of a child whose command line held a URL took 266-311 ms on the game's thread; the same command line again took about 5 ms, and `curl -V` 9 ms (outside the game, 9 ms the first time). Something inspects the new command lines of processes the game starts and remembers them. With a constant command line, `"<System32>\curl.exe" -K -`, and the request given as a curl config on standard input, every start is fast. Starting the same command once in advance with an empty config (curl exits at once with code 2, "no URL specified", sending nothing) takes the first-start cost while the game loads.
- **Quoting a config value:** wrap it in `"`, escape `\` and `"` with a backslash and turn control characters into spaces; then no text can end the value or the line or add an option (checked with curl 8.21.0, including a trailing backslash and an embedded `output = ...`).
- **Google's endpoints (as of 2026-10):** `translate_a/single?client=gtx&dt=t&sl=auto&tl=<target>` replies `[[[part, original, ...], ...], null, "<detected language>", ...]`; `translate_a/t?client=dict-chrome-ex&sl=auto&tl=<target>` (the Chrome extension's client) replies `[["<translation>", "<detected language>"]]` (with a fixed source language, `["<translation>"]`), plain text with no HTML escaping. Both on translate.googleapis.com, the line in `q`. In October 2026 Google began answering `client=gtx` with HTTP 429 and its "automated queries" page for whole networks (both hosts, IPv4 and IPv6, with or without a browser User-Agent) while `dict-chrome-ex` still answered from the same network; Better Chat uses `dict-chrome-ex` first and switches to the other for the session on a 429 or 403, sending the line again at once. Microsoft's keyless Edge translator token (`edge.microsoft.com/translate/auth`) answers 404: gone. Replies arrive in 0.3-1.6 s. Short Latin-script lines are misdetected and the reported confidence does not tell them apart ("ez" came back as Basque with 0.61, "o7" as Arabic with 1.0, a Portuguese sentence 0.57), so Better Chat sends no ASCII-only line with fewer than 4 letters. One HTTP 500 was seen; Better Chat retries a 5xx or a network failure once after 1 s.
- **Language tags:** the game's Text Language and Windows' tags map to Google's codes as pt-BR and pt > pt, other pt-* > pt-PT, zh Hant/TW/HK/MO > zh-TW, other zh > zh-CN, else the language subtag. A player's own language is better taken from Windows' regional format (`GetUserDefaultLocaleName`) than from the game's Text Language or Windows' display language, which are often English.
- The chat font lacks some letters (Vietnamese ones show as `?`).

## Custom service

An OpenAI-compatible chat completions API the player sets in `BetterChat_service.json`, in the folder above the loader's Logs folder (a shared Logs folder never holds the key). Mod Options Menu has no text input, so a file is the only way to give an address and a key.

- **Request:** a POST to `<base_url>/chat/completions` with `{"model", "messages": [system, user]}`: the system message is the prompt with `{language}` replaced by the target language's English name, plus a "Write these terms like this: ..." line for the glossary and game terms the line mentions; the user message is the line as written. No `temperature` or token limit: newer models reject non-default values. The body goes as `data-raw` and the key as a header, both values in curl's config on standard input (never on a command line, never `@file`).
- **Reply:** `choices[1].message.content`. The default prompt asks for `[xx] translation`, so the reply carries the message's language like Google's (the label and the already-in-the-language check work the same); `<think>...</think>` blocks and wrapping quotes are left out. An HTTP error logs the API's `error.type`, never its message (which can quote the key or the line).
- **Addresses:** https, or http only to localhost / 127.0.0.1 / [::1] (local models, which may have no key). A template with example services is written the first time Custom is chosen; every example address answered 401 without a key on 2026-10-19 (DeepSeek `https://api.deepseek.com/v1`, Qwen `https://dashscope.aliyuncs.com/compatible-mode/v1` and `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`, GLM `https://open.bigmodel.cn/api/paas/v4`, OpenAI). A DeepSeek translation took about 1.8 s.
- **Game terms:** into Simplified or Traditional Chinese, the English names of game terms a line mentions (whole words, plural allowed) are given with their Chinese names; into English, the Chinese names with their English ones; the longest term wins over one inside it, 12 at most, the player's glossary first. The 157 terms come from the game's `strings` resources (one file per language; FileDiver reads them, `stingray/strings`). The game's language codes are us gb de es ms fr it jp ko pl pt bp ru cn tc: Simplified Chinese is `cn` (`sc` holds nothing). The Traditional Chinese text has its own names, kept as the game shows them (the Bile Titan is 闊步蟲 in every Traditional Chinese string, Simplified 吐酸泰坦).

## Performance

- `GetAsyncKeyState` took 4-15 ms on some frames in game, with no key pressed and the chat closed. Better Chat reads the keys only while the chat's input is open (its open byte read every 100 ms). `ReadProcessMemory` calls never took more than 0.2 ms.

## Dead ends

- **Writing game.dll's code is detected by GameGuard.** Replacing the 14 game-notice calls to `0x185f470` with 5-byte no-ops through `WriteProcessMemory` worked offline and applied cleanly in game, and each time the game was closed by GameGuard ("suspicious program detected") or crashed within a minute. With that write removed and nothing else changed, sessions ran normally. Write data only (heap, read-write sections), never code. This matches [HD2Runtime](https://github.com/SkyeShade/HD2Runtime), which patches no game code, and [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu), which writes only game.dll's read-write data section.
- **Posting WM_CHAR to the game window does not type into the chat.** The characters are posted but never reach the engine's keystrokes, which are not built from posted WM_CHAR. Use the text setter above.
- **Posting the chat's own send sound** (0xe1ba68c0) plays nothing: the event has no actions.
- **A per-sound volume** through `set_dry_environment_for_source` was not reached: the Lua Wwise world could not be matched to the native one (see above). Editing a sound's volume in its bank changes it everywhere the game plays it and gives one fixed level, not a setting.
- **Showing more chat lines** needs read-only data constants changed (see Height above).

## Signatures

`research/signatures.py` builds these from the game.dll dump and writes them into `better_chat.lua` with the shared signature engine (`tools/sigscan.lua`); `--check` verifies that each matches exactly once and that the script's blocks are current.

| Signature | RVA | Optional | Gives |
|---|---|---|---|
| `chat_send` | 0x186025d | no | the network context global, the chat inside it (+0xc418), the call to the chat's send, the UI sound function, the chat's send sound |
| `chat_ring` | 0x10979dc | no | context, local peer (+0xb398), ring first index and count (+0x9590, +0x9594), line stride (0x228), the game state global |
| `chat_line` | 0x1097b37 | no | a line's sender (+0xb98), time (+0xb90) and text (+0xba0) from the chat |
| `join_feed` | 0x12f21fe | no | the HUD global and active byte, game mode offset, player joined sounds (ship, mission), UI sound function |
| `leave_feed` | 0x12f26d5 | yes | player left sounds (ship, mission) |
| `chat_notice` | 0x12f2f81 | no | the HUD global, the chat widget in the HUD (+0x14498) |
| `tab_button` | 0x17ae42c | yes | the menu tab button's hover and click sounds |
| `button_sounds` | 0x14a47d0 | yes | the standard button's hover and click sounds |
| `option_row` | 0x17fde75 | yes | an option row's change and refused sounds |
| `chat_input` | 0x18608d0 | yes | the chat widget's input-open byte (+0x139b8) |
| `chat_field` | 0x1860200 | yes | the chat's text field (widget + 0x1398) and its update `0x18f2dc0` |
| `field_text` | 0x18f2ef8 | yes | the field's character limit (+0xa84), its text widget (+0x220), the call to the text setter |
| `set_text` | 0x143dd60 | yes | the text setter, its byte limit (0x324) and the widget's text (+0x11c) |
| `play_sound` | 0x1327f50 | no | the UI sound function (must equal the calls read above) |
| `add_line` | 0x10979c0 | yes | the chat's add-line (`chat_ring` must start at its +0x1c) |
| `set_scale` | 0x1447ed0 | yes | the widget scale setter |
| `send_line` | 0x1097560 | yes | the chat's send, by its first 44 bytes (must equal the call in `chat_send`) |
| `send_echo` | 0x10977c4 | yes | inside the send: the context, the local peer and the call to add-line (must equal `add_line`) |

## Research tools

- `research/signatures.py`: the signature spec above; regenerates or checks the script's signature blocks.
- `research/glossary.py`: the game terms for the custom service, from a dump of the game's localized strings (FileDiver; see Custom service); regenerates or checks the script's glossary block.
- `research/sound_ids.py`: every game sound id the code passes to the UI sound function (`0x1327f50`) or to post_audio (`0x12982d0`), with call sites; needs a decrypted game.dll dump and capstone.
- `research/sound_survey.py`: ranks the sounds of chosen banks by loudness (the score above) and writes WAVs to listen to; needs HD2ReAudio's core, [hd2-audio-modder](https://github.com/RaidingForPants/hd2-audio-modder)'s v154 hierarchy parser, vgmstream-cli and numpy.
- `research/clean_chat_texts.tsv`: translated texts written for a chat-cleaning option that was not shipped (see Dead ends).
- `tests/test_release.py`: runs the built entry under LuaJIT against a game.dll dump with the chat ring, HUD, game functions, curl, clipboard and Mod Options Menu simulated.

## Credits and prior art

- [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus; `src/bingus_text.lua` (Zero-Clause BSD) is his.
- [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill), used for the research and the build.
- Mod Lag Watchdog (patpatpatrick's `mod_lag_finder`) measured the mod's frame cost in game.
- spkel-max's pull request #2 proposed outbound translation, the OpenAI-compatible custom service and a built-in Chinese glossary; V6 rebuilt them.
- [FileDiver](https://github.com/xypwn/filediver) reads the game's archives and strings.
