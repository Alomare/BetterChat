"""Better Chat's code signatures (NOTES.md): checked against the game.dll dump and written into better_chat.lua
between the SIGNATURES markers, with the shared signature engine (tools/sigscan.lua) between the SIGNATURE ENGINE
markers.

Globals and offsets are read from the matched code (rip-relative operands, displacements); functions are found by
their own first instructions, or through a call to them. Each feature needs only its own signatures (NOTES.md).

Usage (from the workspace root): python -B mods/BetterChat/research/signatures.py [--check]
  --check   only verify: every signature matches once and the script's blocks are current (exit 1 otherwise)
"""
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
ROOT = MOD.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import sigspec  # noqa: E402

SCRIPT = MOD / 'better_chat.lua'


def function(name, start, end, optional=False):
    """A native function, found by its first instructions (the match is the function's address)."""
    return {'name': name, 'start': start, 'end': end, 'optional': optional}


SPECS = [
    # The chat box's send (inside the HUD chat update 0x185fd10): the network context global, the chat inside it
    # (context + chat), the UI sound function and the chat's own send sound.
    {'name': 'chat_send', 'start': 0x186025d, 'end': 0x1860281,
     'fields': {'context': (0x347cef0, 'rip'), 'chat': (0xc418, 'u32'), 'ui_sound': (0x1327f50, 'call'),
                'send_sound': (0xe1ba68c0, 'u32')}},
    # The chat's add-line (0x10979c0), every received and sent line goes through it: the local peer id in the
    # context, the history ring's first index and line count (64 lines), the line stride.
    {'name': 'chat_ring', 'start': 0x10979dc, 'end': 0x1097ac3,
     'fields': {'context': (0x347cef0, 'rip'), 'local_peer': (0xb398, 'u32'), 'ring_first': (0x9590, 'u32'),
                'ring_count': (0x9594, 'u32'), 'line_stride': (0x228, 'u32'), 'game_state': (0x3326340, 'rip')}},
    # The rest of add-line: the line's sender, time and text.
    {'name': 'chat_line', 'start': 0x1097b37, 'end': 0x1097bfb,
     'fields': {'line_sender': (0xb98, 'u32'), 'line_time': (0xb90, 'u32'), 'line_text': (0xba0, 'u32'),
                'context': (0x347cef0, 'rip'), 'local_peer': (0xb398, 'u32')}},
    # The HUD feed's "player joined" (0x12f21e0): the HUD global and its active byte, the game mode (3 ship,
    # 4 mission) and the notice sound for each.
    {'name': 'join_feed', 'start': 0x12f21fe, 'end': 0x12f2245,
     'fields': {'hud': (0x346d538, 'rip'), 'hud_active': (0x24e335, 'u32'), 'game_state': (0x3326340, 'rip'),
                'mode': (0xac21c, 'u32'), 'join_mission': (0x82250982, 'u32'), 'join_ship': (0xda653421, 'u32'),
                'ui_sound': (0x1327f50, 'call')}},
    # The HUD feed's "player left" (0x12f26b0): its notice sounds (only the sound choice needs them).
    {'name': 'leave_feed', 'start': 0x12f26d5, 'end': 0x12f2706, 'optional': True,
     'fields': {'game_state': (0x3326340, 'rip'), 'mode': (0xac21c, 'u32'), 'leave_mission': (0x3cf15e0, 'u32'),
                'leave_ship': (0xc386a64a, 'u32'), 'ui_sound': (0x1327f50, 'call')}},
    # The chat notice (0x12f2f60): the HUD chat widget inside the HUD (hud + chat_hud).
    {'name': 'chat_notice', 'start': 0x12f2f81, 'end': 0x12f3027,
     'fields': {'hud': (0x346d538, 'rip'), 'hud_active': (0x24e335, 'u32'), 'chat_hud': (0x14498, 'u32')}},
    # Menu sounds (the sound choice; each is optional): the menu tab bar's buttons (init at 0x17ae3xx: hover and
    # click sounds at +0xd40 / +0xd44), ...
    {'name': 'tab_button', 'start': 0x17ae42c, 'end': 0x17ae442, 'optional': True,
     'fields': {'tab_hover': (0x78e15850, 'u32'), 'tab_click': (0xadd37058, 'u32')}},
    # ... the game's standard button sound record (hover +4, click +8), ...
    {'name': 'button_sounds', 'start': 0x14a47d0, 'end': 0x14a47e6, 'optional': True,
     'fields': {'button_hover': (0x65e34ad8, 'u32'), 'button_click': (0x468c8e58, 'u32')}},
    # ... and an option row's arrow (choice change; the refused sound when it can't change).
    {'name': 'option_row', 'start': 0x17fde75, 'end': 0x17fde92, 'optional': True,
     'fields': {'option_click': (0x144418d5, 'u32'), 'option_refused': (0x3e8c63db, 'u32'),
                'ui_sound': (0x1327f50, 'call')}},
    function('play_sound', 0x1327f50, 0x1327f84),      # posts a UI sound event; the first argument is unused
    function('set_scale', 0x1447ed0, 0x1447eec, optional=True),      # widget scale (+0x14, +0x18)
]


def main():
    rows = sigspec.build(SPECS)
    sigspec.report(rows)
    if '--check' in sys.argv:
        problems = sigspec.check(SCRIPT, rows)
        for p in problems:
            print('STALE:', p)
        sys.exit(1 if problems else 0)
    sigspec.write(SCRIPT, rows)
    print('written to', SCRIPT.name)


if __name__ == '__main__':
    main()
