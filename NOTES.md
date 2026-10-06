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

- **Detection:** each frame one 8-byte read of the ring header; new lines = count change + first index change (mod 64); a lower count or another context resets the baseline (no sound for lines already there). Each new line's sender is compared with the local peer id. Your own lines don't alert; muted players' lines never reach the ring.
- **Sound:** choice OFF / Player Joined (default) / Player Left / Menu Tab / Menu Subtab / Option Click, every id read from the code that plays it (the HUD notices with a mission and a ship variant by game mode); 2 s cooldown (frame time). Applying a sound in the menu plays it once. A choice whose signature is missing plays nothing.
- **Size:** set_scale(widget, base * size%), base = the widget's own scale before the mod changed it; re-applied every 30 frames (a new HUD layout resets it), nothing while the widget's scale is 0 (not laid out).
- The mod never writes game memory itself: reads go through ReadProcessMemory; the sound and the size go through the game's own functions.
- Texts: 10 keys in `locales/`, 13 translations using the game's own word for Text Chat.
