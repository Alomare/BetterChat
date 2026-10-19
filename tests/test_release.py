"""Offline test of Better Chat under LuaJIT, with the real game.dll code as fake process memory.

The Ghidra-ready dump (_research/game_25480438.dll, offsets == RVAs) is mapped at a fake base, so the signatures and
the values read from the matched code are checked against the game's own code. The network context (chat ring) and the
HUD (chat widget) are simulated on a fake heap; the game's UI sound, its widget scale setter and Mod Options Menu are
stubs that record their calls. Kernel32 offers only reads; a WriteProcessMemory stub records any write, and the tests
require that there is none: the mod writes no game memory.

Run from the workspace root or the mod folder:  python -B mods/BetterChat/tests/test_release.py
"""
import re
import struct
import sys
import tempfile
from pathlib import Path

from lupa.luajit21 import LuaRuntime

MOD = Path(__file__).resolve().parent.parent
ROOT = MOD.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(MOD / 'research'))
from entry import entry_text  # noqa: E402
import signatures  # noqa: E402
import sigspec  # noqa: E402

SOURCE = entry_text(MOD, 'better_chat.lua')
DUMP = (ROOT / '_research' / 'game_25480438.dll').read_bytes()

CTX, HUD, STATE = 0x20000000, 0x30000000, 0x60000000
CHAT, STRIDE, SENDER, TEXT = 0xc418, 0x228, 0xb98, 0xba0
WIDGET = HUD + 0x14498
OWN, OTHER = 0x1111222233334444, 0x5555666677778888
JOIN_SHIP, JOIN_MISSION, LEFT_SHIP = 0xda653421, 0x82250982, 0xc386a64a
TAB, SUBTAB, OPTION = 0xadd37058, 0x468c8e58, 0x144418d5

HARNESS = r'''
local logdir, image = ...
local real_ffi = require('ffi')
local ffi = real_ffi
local BASE = 0x40000000
fake = {calls = {}, values = {}, specs = {}, changed = {}}
CowboyBingusModLoader = {api = 1, log_directory = logdir .. '/Logs', open_log = function(name)
    if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end
    return io.open(logdir .. '/' .. name, 'w')
end}
local patches, heap = {}, {}
local function read_mem(a, n)
    if a >= BASE and a + n <= BASE + #image then
        local s = image:sub(a - BASE + 1, a - BASE + n)
        for _, p in ipairs(patches) do
            local lo, hi = math.max(a, p[1]), math.min(a + n, p[1] + #p[2])
            if lo < hi then s = s:sub(1, lo - a) .. p[2]:sub(lo - p[1] + 1, hi - p[1]) .. s:sub(hi - a + 1) end
        end
        return s
    end
    for k, v in pairs(heap) do
        if k <= a and a + n <= k + #v then return v:sub(a - k + 1, a - k + n) end
    end
end
local function write_mem(a, s)
    for k, v in pairs(heap) do
        if k <= a and a + #s <= k + #v then
            heap[k] = v:sub(1, a - k) .. s .. v:sub(a - k + #s + 1)
            return true
        end
    end
    return false
end
fake.patch = function(rva, bytes) patches[#patches + 1] = {BASE + rva, bytes} end
fake.heap = function(a, bytes) heap[a] = bytes end
local function addr(p) return tonumber(ffi.cast('uint64_t', p)) end
local k32 = {
    better_chat_GetCurrentProcess = function() return nil end,
    better_chat_GetModuleHandleA = function(name) return ffi.cast('void *', BASE) end,
    better_chat_ReadProcessMemory = function(p, a, buf, size, got)
        local s = read_mem(addr(a), tonumber(size))
        if not s then return 0 end
        ffi.copy(buf, s, #s); got[0] = #s; return 1
    end,
}
-- Processes and pipes (translation): curl is never started; a test writes its reply with fake.reply.
local handles, next_handle = {}, 0x100
local function new_handle(obj) next_handle = next_handle + 4; handles[next_handle] = obj; return ffi.cast('void *', next_handle) end
local function H(h) return handles[tonumber(ffi.cast('uint64_t', h))] end
local function wstr(p) local t, i = {}, 0; while p[i] ~= 0 do t[#t + 1] = string.char(p[i]); i = i + 1 end; return table.concat(t) end
fake.processes, fake.qpc, fake.closed = {}, 0, 0
k32.better_chat_QueryPerformanceFrequency = function(f) f[0] = 1000; return 1 end
k32.better_chat_QueryPerformanceCounter = function(t) t[0] = fake.qpc; return 1 end
k32.better_chat_GetSystemDirectoryW = function(buf, n)
    local s = 'C:\\Windows\\system32'
    for i = 1, #s do buf[i - 1] = s:byte(i) end
    buf[#s] = 0
    return #s
end
k32.better_chat_GetFileAttributesW = function(p) fake.curl_checked = wstr(p); return fake.no_curl and 0xffffffff or 0x20 end
k32.better_chat_GetLastError = function() return 5 end
k32.better_chat_CreatePipe = function(r, w, sa, size)
    assert(sa.bInheritHandle == 1, 'pipe handles must be inheritable')
    local pipe = {data = ''}
    r[0] = new_handle({pipe = pipe}); w[0] = new_handle({pipe = pipe})
    return 1
end
k32.better_chat_SetHandleInformation = function(h, mask, flags) H(h).private = mask == 1 and flags == 0; return 1 end
k32.better_chat_InitializeProcThreadAttributeList = function(list, n, flags, size)
    if list == nil then size[0] = 48; return 0 end
    return 1
end
k32.better_chat_UpdateProcThreadAttribute = function(list, flags, attribute, value, size)
    fake.handle_list = tonumber(attribute) == 0x20002 and tonumber(size) == 16
    return 1
end
k32.better_chat_DeleteProcThreadAttributeList = function() end
k32.better_chat_CreateProcessW = function(app, cmd, pa, ta, inherit, flags, env, dir, si, info)
    if fake.spawn_fails then return 0 end
    local p = {app = wstr(app), cmd = wstr(cmd), dir = wstr(dir), flags = flags,
               stdin = H(si.StartupInfo.hStdInput).pipe, stdout = H(si.StartupInfo.hStdOutput).pipe,
               private = H(si.StartupInfo.hStdInput).private or H(si.StartupInfo.hStdOutput).private}
    fake.processes[#fake.processes + 1] = p
    info.hProcess = new_handle({process = p}); info.hThread = new_handle({})
    fake.qpc = fake.qpc + (fake.spawn_cost or 0)
    return 1
end
k32.better_chat_WriteFile = function(h, buf, n, done)
    local pipe = H(h).pipe
    pipe.data = pipe.data .. buf:sub(1, n); done[0] = n
    return 1
end
k32.better_chat_ReadFile = function(h, buf, n, done)
    local pipe = H(h).pipe
    local s = pipe.data:sub(1, n)
    ffi.copy(buf, s, #s); pipe.data = pipe.data:sub(#s + 1); done[0] = #s
    return 1
end
k32.better_chat_PeekNamedPipe = function(h, b, n, r, available) available[0] = #H(h).pipe.data; return 1 end
k32.better_chat_WaitForSingleObject = function(h) return H(h).process.exit and 0 or 0x102 end
k32.better_chat_GetExitCodeProcess = function(h, code) code[0] = H(h).process.exit or 259; return 1 end
k32.better_chat_TerminateProcess = function(h, c) local p = H(h).process; p.exit, p.terminated = c, true; return 1 end
k32.better_chat_CloseHandle = function(h) fake.closed = fake.closed + 1; return 1 end
fake.reply = function(i, body, status, exit)
    local p = fake.processes[i]
    p.stdout.data = p.stdout.data .. body .. '\n@@ ' .. (status or '200')
    p.exit = exit or 0
end
-- user32 and the clipboard (paste): keys held in fake.held, the clipboard as UTF-16 units in fake.clipboard.
fake.held, fake.posted, fake.foreground, fake.window_pid = {}, {}, 0x9000, 4242
k32.better_chat_GetCurrentProcessId = function() return 4242 end
fake.region, fake.display = 'en-US', 'en-US'
local function put(buf, s)
    if not s then return 0 end
    for i = 1, #s do buf[i - 1] = s:byte(i) end
    buf[#s] = 0
    return #s + 1
end
k32.better_chat_GetUserDefaultUILanguage = function() return 0x409 end
k32.better_chat_LCIDToLocaleName = function(lcid, buf, size, flags) return put(buf, fake.display) end
k32.better_chat_GetUserDefaultLocaleName = function(buf, size) return put(buf, fake.region) end
k32.better_chat_GlobalLock = function(h)
    local n = #fake.clipboard
    fake.clip_buf = ffi.new('uint16_t[?]', n + 1)
    for i = 1, n do fake.clip_buf[i - 1] = fake.clipboard[i] end
    return fake.clip_buf
end
k32.better_chat_GlobalSize = function(h) return (#fake.clipboard + 1) * 2 end
k32.better_chat_GlobalUnlock = function(h) fake.unlocked = (fake.unlocked or 0) + 1; return 1 end
user32 = {
    better_chat_GetAsyncKeyState = function(key)
        fake.key_reads = (fake.key_reads or 0) + 1
        fake.key_counts = fake.key_counts or {}
        fake.key_counts[key] = (fake.key_counts[key] or 0) + 1
        return fake.held[key] and -32768 or 0
    end,
    better_chat_GetForegroundWindow = function() return fake.foreground and ffi.cast('void *', fake.foreground) or nil end,
    better_chat_GetWindowThreadProcessId = function(w, pid) pid[0] = fake.window_pid; return 1 end,
    better_chat_PostMessageW = function(w, message, wparam, lparam)
        fake.posted[#fake.posted + 1] = string.format('%x %x %x %d', tonumber(ffi.cast('uint64_t', w)), message,
                                                      tonumber(wparam), tonumber(lparam))
        return 1
    end,
    better_chat_OpenClipboard = function() if fake.clipboard_busy then return 0 end; fake.opened = (fake.opened or 0) + 1; return 1 end,
    better_chat_CloseClipboard = function() fake.closed_clipboard = (fake.closed_clipboard or 0) + 1; return 1 end,
    better_chat_GetClipboardData = function(format)
        if format ~= 13 or not fake.clipboard then return nil end
        return ffi.cast('void *', 0x7000)
    end,
}
local function floats(v) return string.format('%.3f,%.3f', v.x, v.y) end
package.loaded.ffi = setmetatable({
    load = function(name)
        if name == 'user32' then return user32 end
        assert(name == 'kernel32', 'unexpected library ' .. name); return k32
    end,
    cast = function(t, v)
        if t == 'BetterChatSound' then
            local rva = tonumber(v) - BASE
            return function(unused, id)
                fake.calls[#fake.calls + 1] = string.format('sound %x %x', rva, id)
                fake.qpc = fake.qpc + (fake.sound_cost or 0)
            end
        end
        if t == 'BetterChatSetVec' then
            local rva = tonumber(v) - BASE
            return function(widget, value)
                fake.calls[#fake.calls + 1] = string.format('vec %x %x %s', rva, widget, floats(value))
                write_mem(widget + 0x14, ffi.string(ffi.new('float[2]', value.x, value.y), 8))
            end
        end
        if t == 'BetterChatSetText' then
            local rva = tonumber(v) - BASE
            return function(widget, text)
                assert(type(text) == 'string' and #text < 0x324, 'set_text text of 0x324 bytes or more')
                fake.calls[#fake.calls + 1] = string.format('text %x %s', widget, text)
                local old = read_mem(widget + 0x11c, 0x325)
                write_mem(widget + 0x11c, text .. '\0')
                return old:match('^[^%z]*') ~= text and 1 or 0
            end
        end
        if t == 'BetterChatAddLine' then
            local rva = tonumber(v) - BASE
            return function(chat, sender, text)
                assert(type(text) == 'string' and #text <= 0x200, 'add-line text over 0x200 bytes')
                fake.calls[#fake.calls + 1] = string.format('line %x %x %s %s', rva, chat, tostring(sender), text)
                if fake.on_add_line then fake.on_add_line(tostring(sender), text) end
            end
        end
        if t == 'BetterChatSend' then
            local rva = tonumber(v) - BASE
            return function(chat, unused, text)
                assert(type(text) == 'string' and #text < 0x200, 'send text of 0x200 bytes or more')
                fake.calls[#fake.calls + 1] = string.format('send %x %x %s', rva, chat, text)
                -- The game's send ends with the line in the local chat (its add-line), unless it refuses it.
                if fake.on_send and not (fake.refuse and fake.refuse(text)) then fake.on_send(text) end
            end
        end
        return real_ffi.cast(t, v)
    end}, {__index = real_ffi})
-- Mod Options Menu (installed by tests that set ModOptionsMenu = fake.menu).
fake.menu = {api = 1, version = 3,
    register_option = function(id, spec) fake.specs[id] = spec; fake.order = (fake.order or '') .. id .. ' '; return true end,
    get = function(id) return fake.values[id] end,
    on_change = function(id, fn) fake.changed[id] = fn; return true end}
function fake.setvec(a, x, y) return write_mem(a, ffi.string(ffi.new('float[2]', x, y), 8)) end
function fake.vec(a) local v = ffi.new('float[2]'); ffi.copy(v, read_mem(a, 8), 8); return string.format('%.3f,%.3f', v[0], v[1]) end
'''


class World:
    """The simulated game objects; push() puts them on the fake heap."""

    def __init__(self, lua):
        self.f = lua.globals().fake
        self.ctx = bytearray(0x16000)
        struct.pack_into('<Q', self.ctx, 0xb398, OWN)
        self.ctx[CHAT] = 1
        self.hud = bytearray(0x14498 + 0x139c0)
        self.state = bytearray(0xac220)
        self.mode(3)
        self.f.patch(0x347cef0, struct.pack('<Q', CTX))
        self.f.patch(0x346d538, struct.pack('<Q', HUD))
        self.f.patch(0x3326340, struct.pack('<Q', STATE))
        self.first = self.count = 0
        self.push_all()

    def mode(self, m):
        struct.pack_into('<I', self.state, 0xac21c, m)

    def push_all(self):
        self.f.heap(CTX, bytes(self.ctx))
        self.f.heap(HUD, bytes(self.hud))
        self.f.heap(STATE, bytes(self.state))

    def push_ctx(self):
        self.f.heap(CTX, bytes(self.ctx))

    def add(self, sender, text=b'hello', push=True):
        """Adds a line the way the game's add-line does (ring of 64)."""
        slot = (self.first + self.count) % 64
        if self.count == 64:
            self.first = (self.first + 1) % 64
        else:
            self.count += 1
        base = CHAT + slot * STRIDE
        struct.pack_into('<Q', self.ctx, base + SENDER, sender)
        self.ctx[base + TEXT:base + TEXT + 0x201] = text.ljust(0x201, b'\0')
        struct.pack_into('<II', self.ctx, CHAT + 0x9590, self.first, self.count)
        if push:
            self.push_ctx()

    def widget(self, scale):
        struct.pack_into('<ff', self.hud, 0x14498 + 0x14, *scale)
        self.f.heap(HUD, bytes(self.hud))


def new_lua(logdir):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(HARNESS, str(logdir), DUMP)
    return lua


def run():
    ok = []

    def check(cond, what):
        ok.append(bool(cond))
        print('PASS' if cond else 'FAIL', what)

    check(not sigspec.check(signatures.SCRIPT, sigspec.build(signatures.SPECS)),
          "the script's signature blocks match research/signatures.py")

    # --- Without Mod Options Menu: the defaults (sound: player joined notice on the ship, action wheel in missions).
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    w.add(OTHER, push=False)
    w.add(OWN)
    lua.execute(SOURCE)
    lua.execute('for i = 1, 20 do update(0.016) end')
    M = lua.globals().BetterChat
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    status = lambda: (logdir / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    check(M.ready, 'ready: every signature at its rva, values read')
    check('Ready: chat = context + 0xc418, ring at +0x9590 (stride 0x228, sender +0xb98); sound ready, scale ready, translate ready, show ready, paste ready, outbound ready; '
          'sounds: joined 0xda653421/0x82250982, left 0xc386a64a/0x03cf15e0, '
          'tab 0xadd37058/0xadd37058, subtab 0x468c8e58/0x468c8e58, option 0x144418d5/0x144418d5, '
          'confirm 0x7a69c309, back 0x96c8c848, wheel 0x22200946, purchase 0xa1af099e, dialog 0xd8fc9d33' in log(),
          'offsets and every sound id from code, every feature ready')
    check('WriteProcessMemory' not in SOURCE and 'VirtualProtect' not in SOURCE,
          'the script has no way to write memory (no WriteProcessMemory, no VirtualProtect)')
    check(status().startswith('OK - watching the chat'), 'status OK: %r' % status().splitlines()[0])
    check(len(f.calls) == 0 and 'Chat history: context 0x20000000, first 0, count 2' in log(),
          'lines already in the history make no sound')
    # Another player's line: at the next check (every 200 ms), the ship's join notice.
    w.add(OTHER)
    lua.execute('update(0.1)')
    check(len(f.calls) == 0, 'a new line waits for the next check (200 ms)')
    lua.execute('update(0.15)')
    calls = list(f.calls.values())
    check(calls == ['sound 1327f50 %x' % JOIN_SHIP], "another player's line: the join notice sound: %r" % calls)
    check('Line 2: sender 5555666677778888, 5 bytes' in log(), 'the line is logged without its text')
    # Your own line: nothing (after the cooldown).
    lua.execute('update(3.0)')
    w.add(OWN)
    lua.execute('update(0.25)')
    check(len(f.calls) == 1 and '1 new chat line(s), 0 from other players' in log(), 'your own line: no sound')
    # Cooldown: a second line within 2 s is quiet, one after 2 s plays.
    w.add(OTHER)
    lua.execute('update(0.5)')
    w.add(OTHER)
    lua.execute('update(1.0)')
    check(len(f.calls) == 2 and 'Sound skipped (cooldown)' in log(), 'a line within 2 seconds of the sound is quiet')
    lua.execute('update(1.0)')
    w.add(OTHER)
    lua.execute('update(0.25)')
    check(len(f.calls) == 3, 'a line 2 seconds after the sound plays it')
    # A full ring: the count stays at 64 and the first index moves.
    lua.execute('update(3.0)')
    while w.count < 64:
        w.add(OWN, push=False)
    w.push_ctx()
    lua.execute('update(0.25)')
    check(len(f.calls) == 3, 'filling the ring with your own lines: no sound')
    w.add(OTHER)
    lua.execute('update(0.25)')
    check(w.first == 1 and len(f.calls) == 4, 'a full ring (count 64, first index moves): the new line is seen')
    # Missions: the mission's join notice.
    lua.execute('update(3.0)')
    w.mode(4)
    w.push_all()
    w.add(OTHER)
    lua.execute('update(0.25)')
    check(list(f.calls.values())[-1] == 'sound 1327f50 %x' % 0x22200946, 'in missions: the action wheel (default)')
    # A cleared history (count back to 0): new baseline, no sound.
    n = len(f.calls)
    w.first = w.count = 0
    struct.pack_into('<II', w.ctx, CHAT + 0x9590, 0, 0)
    w.push_ctx()
    lua.execute('update(3.0)')
    check(len(f.calls) == n and 'first 0, count 0' in log(), 'a cleared history is a new baseline')
    # The default leaves the size alone.
    check('Chat scale' not in log(), 'default: chat size untouched')

    # --- Mod Options Menu: the options in menu order, texts as functions, values applied.
    logdir2 = Path(tempfile.mkdtemp())
    lua2 = new_lua(logdir2)
    w2 = World(lua2)
    f2 = w2.f
    lua2.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.alert"] = false; '
                 'fake.values["alomare.better_chat.inbound_language"] = 1')
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 5 do update(0.016) end')
    log2 = lambda: (logdir2 / 'BetterChat.log').read_text(encoding='utf-8')
    order = f2.order.split()
    s = f2.specs
    menu = ('scale', 'alert', 'alert_ship', 'alert_mission', 'service', 'inbound_language', 'outbound_language',
            'translate_own')
    check(order == ['alomare.better_chat.' + n for n in menu], 'options registered in menu order (no paste option): %r' % order)
    gaps = [n for n in menu if s['alomare.better_chat.' + n].gap]
    check(gaps == ['alert', 'service', 'translate_own'], 'a gap above Sound Alert, Translation Service and Inbound Debug: %r' % gaps)
    alert = s['alomare.better_chat.alert']
    check(alert.type == 'toggle' and alert.default is True and alert.label() == 'Sound Alert', 'Sound Alert: a toggle, on by default')
    sound = s['alomare.better_chat.alert_ship']
    names = [sound.choices[i]() for i in range(1, 11)]
    check(sound.type == 'choice' and len(sound.choices) == 10
          and names == ['Player Joined', 'Player Left', 'Menu Tab', 'Menu Subtab', 'Option Click', 'Menu Confirm',
                        'Menu Back', 'Action Wheel', 'Item Purchase', 'Confirmation Dialog']
          and sound.default == 1 and sound.label() == 'Sound Alert in Ship' and sound.mod() == 'Better Chat'
          and sound.mod_id == 'alomare.better_chat', 'ship sound: the game sounds (no OFF), Player Joined by default, texts as functions')
    mission = s['alomare.better_chat.alert_mission']
    check(mission.type == 'choice' and len(mission.choices) == 12 and mission.default == 8
          and [mission.choices[i]() for i in range(1, 11)] == names
          and [mission.choices[i]() for i in (11, 12)] == ['Reinforce Request', 'Countdown']
          and mission.label() == 'Sound Alert in Mission',
          'mission sound: the same sounds, then the two only the mission bank has; Action Wheel by default')
    debug = s['alomare.better_chat.translate_own']
    check(debug.type == 'toggle' and debug.default is False and debug.label() == 'Inbound Debug', 'Inbound Debug: off by default')
    sc = s['alomare.better_chat.scale']
    check(sc.type == 'slider' and sc.min == 50 and sc.max == 200 and sc.step == 5 and sc.default == 100
          and not sc.gap and sc.label() == 'Chat Size (%)', 'size slider: 50-200% in steps of 5, 100 by default')
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(len(f2.calls) == 0 and '1 new chat line(s), 1 from other players' in log2(), 'Sound Alert off: no sound')
    lua2.execute('fake.changed["alomare.better_chat.alert"](true)')
    check(len(f2.calls) == 0, 'turning Sound Alert on plays nothing')
    for choice, want, what in ((3, TAB, 'menu tab'), (4, SUBTAB, 'menu subtab'), (6, 0x7a69c309, 'menu confirm'),
                               (7, 0x96c8c848, 'menu back'), (8, 0x22200946, 'action wheel'),
                               (9, 0xa1af099e, 'item purchase'), (10, 0xd8fc9d33, 'confirmation dialog'),
                               (5, OPTION, 'option click')):
        f2.calls = lua2.table()
        lua2.execute('fake.changed["alomare.better_chat.alert_ship"](%d)' % choice)
        check(list(f2.calls.values()) == ['sound 1327f50 %x' % want], 'picking %s plays it once (preview)' % what)
    for choice, want, what in ((11, 0x4a300afb, 'reinforce request'), (12, 0x9da28dab, 'countdown')):
        f2.calls = lua2.table()
        lua2.execute('fake.changed["alomare.better_chat.alert_mission"](%d)' % choice)
        check(list(f2.calls.values()) == ['sound 1327f50 %x' % want], 'picking %s for missions plays it once (preview)' % what)
    lua2.execute('fake.changed["alomare.better_chat.alert_ship"](11)')
    check('Option alert_ship = 1' in log2(), 'the ship option has no mission-only sound: index 11 falls back to the default')
    lua2.execute('fake.changed["alomare.better_chat.alert_ship"](5)')
    lua2.execute('update(3.0)')
    f2.calls = lua2.table()
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(list(f2.calls.values()) == ['sound 1327f50 %x' % OPTION], 'the picked sound plays for new messages')
    check('Slow update' not in log2(), 'normal updates are not logged as slow')
    lua2.execute('update(3.0)')
    w2.add(OTHER)
    lua2.execute('fake.sound_cost = 12; update(0.25); fake.sound_cost = 0')
    check('Slow update: 12.0 ms (chat 12.0, paste 0.0, outbound 0.0, translate 0.0, show 0.0, scale 0.0, other 0.0; '
          'inside them: sound 12.0, curl start 0.0, log 0.0 in 3 lines)' in log2(),
          'a slow sound call is logged as a slow update with what took the time')
    # In a mission the mission's choice plays, not the ship's.
    lua2.execute('fake.changed["alomare.better_chat.alert_mission"](6); update(3.0)')
    w2.mode(4)
    w2.push_all()
    f2.calls = lua2.table()
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(list(f2.calls.values()) == ['sound 1327f50 %x' % 0x7a69c309], "in a mission: the mission option's sound")
    w2.mode(3)
    w2.push_all()
    lua2.execute('update(3.0)')
    f2.calls = lua2.table()
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(list(f2.calls.values()) == ['sound 1327f50 %x' % OPTION], "back on the ship: the ship option's sound")
    # Your own lines: quiet.
    lua2.execute('update(3.0)')
    f2.calls = lua2.table()
    w2.add(OWN)
    lua2.execute('update(0.25)')
    check(len(f2.calls) == 0 and '1 new chat line(s), 0 from other players, 1 from you' in log2(), 'your own line: no sound')
    # Sound Alert off again: quiet, whatever the sounds picked.
    lua2.execute('fake.changed["alomare.better_chat.alert"](false); update(3.0)')
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(len(f2.calls) == 0, 'Sound Alert turned off: no sound')
    # Size: scaled from the widget's own scale once it is laid out.
    f2.calls = lua2.table()
    lua2.execute('fake.changed["alomare.better_chat.scale"](150); update(0.016)')
    check(len(f2.calls) == 0, 'a widget not laid out yet (scale 0) is left alone')
    w2.widget((1, 1))
    lua2.execute('for i = 1, 30 do update(0.016) end')
    check(list(f2.calls.values()) == ['vec 1447ed0 %x 1.500,1.500' % WIDGET], 'size 150%: set_scale(1.5, 1.5)')
    w2.widget((0, 0))  # the HUD torn down (loading)
    lua2.execute('for i = 1, 30 do update(0.016) end')
    check(len(f2.calls) == 1, 'a torn-down widget (scale 0) is left alone')
    w2.widget((1, 1))  # a new HUD layout
    lua2.execute('for i = 1, 30 do update(0.016) end')
    check(list(f2.calls.values())[-1] == 'vec 1447ed0 %x 1.500,1.500' % WIDGET and len(f2.calls) == 2,
          'a widget back at the game size is scaled again')
    lua2.execute('fake.changed["alomare.better_chat.scale"](100); update(0.016)')
    check(list(f2.calls.values())[-1] == 'vec 1447ed0 %x 1.000,1.000' % WIDGET, 'size back to 100%: scale 1')
    # --- Mod Options Menu v1.0 (version 1): plain strings.
    lua3 = new_lua(Path(tempfile.mkdtemp()))
    World(lua3)
    lua3.execute('fake.menu.version = 1; ModOptionsMenu = fake.menu')
    lua3.execute(SOURCE)
    lua3.execute('update(0.016)')
    s3 = lua3.globals().fake.specs['alomare.better_chat.alert_ship']
    check(s3.label == 'Sound Alert in Ship' and s3.choices[3] == 'Menu Tab', 'v1.0: texts as strings')

    # --- set_scale moved out of reach: only the size is off.
    logdir4 = Path(tempfile.mkdtemp())
    lua4 = new_lua(logdir4)
    w4 = World(lua4)
    w4.f.patch(0x1447ed0, b'\xcc' * 8)
    lua4.execute(SOURCE)
    lua4.execute('for i = 1, 80 do update(0.016) end')
    log4 = (logdir4 / 'BetterChat.log').read_text(encoding='utf-8')
    M4 = lua4.globals().BetterChat
    check(M4.ready and 'scale off (code not found: set_scale (not found))' in log4 and 'sound ready' in log4,
          'set_scale not found: only the size is off')

    # --- The menu tab's code changed: that sound is missing, the others play.
    logdir6 = Path(tempfile.mkdtemp())
    lua6 = new_lua(logdir6)
    w6 = World(lua6)
    w6.f.patch(0x17ae42c, b'\xcc' * 4)
    lua6.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.alert_ship"] = 3')
    lua6.execute(SOURCE)
    lua6.execute('for i = 1, 80 do update(0.016) end')
    log6 = (logdir6 / 'BetterChat.log').read_text(encoding='utf-8')
    w6.add(OTHER)
    lua6.execute('update(0.25)')
    check('tab missing' in log6 and len(w6.f.calls) == 0, 'a missing menu sound plays nothing')

    # --- The chat ring's code changed: the mod does nothing.
    logdir5 = Path(tempfile.mkdtemp())
    lua5 = new_lua(logdir5)
    w5 = World(lua5)
    w5.f.patch(0x1097a7c, b'\xcc' * 4)
    lua5.execute(SOURCE)
    lua5.execute('for i = 1, 80 do update(0.016) end')
    st5 = (logdir5 / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    M5 = lua5.globals().BetterChat
    check(M5.retired and st5.startswith('NOT AVAILABLE - code not found: chat_ring'), 'chat ring missing: retired, '
          'game unchanged: %r' % st5.splitlines()[0])

    run_translation(check)
    run_paste(check)
    run_translate_to(check)
    run_outbound(check)
    run_service(check)

    print('%d/%d' % (sum(ok), len(ok)))
    return all(ok)


def run_paste(check):
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    field = 0x14498 + 0x1398
    text_at = field + 0x220 + 0x11c
    struct.pack_into('<I', w.hud, field + 0xa84, 120)  # the chat keeps 119 characters
    w.hud[text_at:text_at + 3] = b'hi '
    f.heap(HUD, bytes(w.hud))
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    check('paste ready' in log(), 'paste ready: the text setter and the chat field found')
    open_at = 0x14498 + 0x139b8

    def chat(is_open):
        w.hud[open_at] = 1 if is_open else 0
        f.heap(HUD, bytes(w.hud))
        lua.execute('update(0.1)')  # the open flag is read every 100 ms

    def field_text(text):
        w.hud[text_at:text_at + 0x325] = text.ljust(0x325, b'\0')
        f.heap(HUD, bytes(w.hud))

    def clipboard(text):
        units = list(struct.unpack('<%dH' % (len(text.encode('utf-16-le')) // 2), text.encode('utf-16-le')))
        f.clipboard = lua.table(*units)

    def ctrl_v():
        f.held[0x11] = True
        f.held[0x56] = True
        lua.execute('update(0.016)')
        f.held[0x56] = None
        f.held[0x11] = None
        lua.execute('update(0.016)')

    def set_calls():
        return [c for c in f.calls.values() if c.startswith('text ')]

    def last_text():
        return set_calls()[-1].split(' ', 2)[2].encode('utf-8')

    clipboard('hello\r\nworld\tok \U0001F600 été  ')
    chat(False)
    f.key_reads = 0
    lua.execute('for i = 1, 60 do update(0.016) end')
    check(f.key_reads == 0, 'chat closed: no key state read in 60 frames (%d)' % f.key_reads)
    ctrl_v()
    check(not set_calls() and not f.opened, 'Ctrl+V with the chat closed: nothing (the clipboard is not read)')
    chat(True)
    f.held[0x56] = True
    lua.execute('update(0.016)')
    f.held[0x56] = None
    lua.execute('update(0.016)')
    check(not set_calls(), 'V without Ctrl: nothing')
    ctrl_v()
    want = 'text %x hi hello world ok été' % (HUD + field + 0x220)
    check(set_calls() == [want] and f.opened == 1 and f.closed_clipboard == 1 and f.unlocked == 1,
          "Ctrl+V: the clipboard added to the chat's text through the game's setter, line breaks and tabs as "
          "spaces, emoji left out: %r" % set_calls())
    check('Paste: 20 bytes added (limit 119 characters)' in log() and 'hello' not in log(), 'the paste is logged without its text')
    # The chat's character limit (119 here) and the setter's byte limit (under 0x324), on character boundaries.
    field_text(b'')
    clipboard('a' * 1000)
    ctrl_v()
    check(last_text() == b'a' * 119, "the chat's character limit: %d" % len(last_text()))
    struct.pack_into('<I', w.hud, field + 0xa84, 0)  # unreadable limit: only the byte limit
    field_text(b'x' * 100)
    clipboard('漢' * 300)
    ctrl_v()
    got = last_text()
    check(len(got) <= 0x323 and got.decode('utf-8') == 'x' * 100 + '漢' * 234,
          'the byte limit on a character boundary: %d bytes' % len(got))
    struct.pack_into('<I', w.hud, field + 0xa84, 120)
    f.heap(HUD, bytes(w.hud))
    # Holding Ctrl+V pastes once; another window in front, a busy or empty clipboard: nothing.
    field_text(b'')
    n = len(set_calls())
    clipboard('again')
    f.held[0x11] = True
    f.held[0x56] = True
    lua.execute('for i = 1, 5 do update(0.016) end')
    f.held[0x56] = None
    f.held[0x11] = None
    lua.execute('update(0.016)')
    check(len(set_calls()) == n + 1, 'holding Ctrl+V pastes once')
    f.window_pid = 1
    ctrl_v()
    check(len(set_calls()) == n + 1, "another program's window in front: nothing")
    f.window_pid = 4242
    f.clipboard_busy = True
    ctrl_v()
    check('Paste: clipboard busy' in log(), 'a busy clipboard is logged')
    f.clipboard_busy = None
    f.clipboard = None
    ctrl_v()
    check('Paste: no text in the clipboard' in log() and f.opened == f.closed_clipboard,
          'no text in the clipboard: logged, the clipboard closed')
    # Paste has no setting: it is always on.
    lua.execute('ModOptionsMenu = fake.menu; update(0.016)')
    check(f.specs['alomare.better_chat.paste'] is None, 'no paste option is registered')

    # The text setter moved: paste off, the rest works.
    logdir2 = Path(tempfile.mkdtemp())
    lua2 = new_lua(logdir2)
    World(lua2)
    lua2.globals().fake.patch(0x143dd60, b'\xcc' * 4)
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 80 do update(0.016) end')
    st2 = (logdir2 / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    check('paste off (code not found: set_text (not found))' in st2 and st2.startswith('OK'),
          'text setter not found: only paste is off')


def run_translate_to(check):
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    f.region, f.display = 'pt-BR', 'en-US'
    lua.execute('ModOptionsMenu = fake.menu')
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    spec = f.specs['alomare.better_chat.inbound_language']
    names = [spec.choices[i]() if callable(spec.choices[i]) else spec.choices[i] for i in range(1, len(spec.choices) + 1)]
    check(spec.type == 'choice' and spec.default == 2 and len(names) == 16
          and names[:4] == ['OFF', 'Automatic', 'Game Language', 'English']
          and names[9] == 'Português (Brasil)' and spec.label() == 'Inbound Language'
          and 'Translation Service' in spec.description(),
          'Inbound Language: OFF, Automatic (default), game language, 13 languages: %r' % names)
    check('Windows: regional format pt-BR, display language en-US (Automatic: pt)' in log(),
          "Windows' regional format and display language read")
    finish_warmup(lua, f, log, check, 'on by default: at load')

    def target(line):
        w.add(OTHER, line)
        lua.execute('update(0.25)')
        url = curl_options(f.processes[len(f.processes)])['url']
        f.reply(len(f.processes), google('x', 'en'))
        lua.execute('update(0.016)')
        return url.rsplit('tl=', 1)[1]

    check(target(b'hello there') == 'pt', 'Automatic: the regional format (pt-BR) wins over an English Windows')
    f.region = None
    lua.execute('BetterChat._test.reread_windows()')
    check(target(b'hello you') == 'en', 'Automatic without a regional format: the display language')
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](3)')
    game = re.search(r'Text language: (\S+)', log()).group(1)
    check(target(b'hello again') == {'pt-BR': 'pt', 'zh-Hans': 'zh-CN'}.get(game, game), 'Game Language: the Text Language')
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](11)')
    check(target(b'hello once more') == 'pt-PT', 'an explicit language: Português (Portugal) is pt-PT')
    # Already in the target's language: Brazilian Portuguese is not translated to European Portuguese.
    w.add(OTHER, b'bom dia pessoal')
    lua.execute('update(0.25)')
    f.reply(len(f.processes), google('bom dia pessoal', 'pt'))
    lua.execute('update(0.016)')
    check('not shown: already in pt-PT' in log(), 'pt is already pt-PT (same language)')
    gc = lua.globals().BetterChat._test.google_code
    codes = {t: gc(t) for t in ('pt-BR', 'pt-PT', 'pt', 'zh-CN', 'zh-Hant-TW', 'zh-HK', 'zh-SG', 'es-419', 'nl-NL', 'en-US', 'fil-PH')}
    check(codes == {'pt-BR': 'pt', 'pt-PT': 'pt-PT', 'pt': 'pt', 'zh-CN': 'zh-CN', 'zh-Hant-TW': 'zh-TW', 'zh-HK': 'zh-TW',
                    'zh-SG': 'zh-CN', 'es-419': 'es', 'nl-NL': 'nl', 'en-US': 'en', 'fil-PH': 'fil'},
          'language tags to Google codes: %r' % codes)


def curl_config(data):
    """curl's config (-K) as curl reads it: one option per line, `name = value` or a bare name; a value in quotes
    ends at the first unescaped quote, with \\\\, \\", \\n, \\t, \\r, \\v escapes (a backslash before anything else is
    dropped). Returns [(name, value or None, what follows a quoted value)]: anything after the closing quote is how
    a line could smuggle in more."""
    out = []
    for line in data.split('\n'):
        line = line.lstrip(' \t')
        if not line or line[0] == '#':
            continue
        i = 0
        while i < len(line) and line[i] not in ' \t=:':
            i += 1
        name, rest = line[:i], line[i:].lstrip(' \t')
        if rest[:1] in ('=', ':'):
            rest = rest[1:].lstrip(' \t')
        if not rest:
            out.append((name, None, ''))
        elif rest[0] == '"':
            value, j, esc = [], 1, {'t': '\t', 'n': '\n', 'r': '\r', 'v': '\v'}
            while j < len(rest) and rest[j] != '"':
                if rest[j] == '\\' and j + 1 < len(rest):
                    j += 1
                    value.append(esc.get(rest[j], rest[j]))
                else:
                    value.append(rest[j])
                j += 1
            out.append((name, ''.join(value), rest[j + 1:]))
        else:
            out.append((name, rest.split()[0], ' '.join(rest.split()[1:])))
    return out


def curl_options(p):
    """A started curl's options: its command line must be the constant one; the rest is the config on its input."""
    assert p.cmd == '"C:\\Windows\\system32\\curl.exe" -K -', p.cmd
    return {name: value for name, value, _ in curl_config(p.stdin.data)}


def finish_warmup(lua, f, log, check, when, start_ms=0):
    """The curl warm-up, started once translation is on: checked and answered, then taken out of the fake process list
    (its handles out of the count), so that the tests number the translation processes from 1."""
    w = f.processes[1] if len(f.processes) == 1 else None
    check(w is not None and w.cmd == '"C:\\Windows\\system32\\curl.exe" -K -' and w.stdin.data == ''
          and w.flags == 0x08000000 + 0x80000 and not w.private,
          'translation on (%s): one curl first, the same command line, an empty config (nothing sent), '
          'no chat line started before it' % when)
    if w is None:
        return
    w.stdout.data = 'curl: no URL specified!'
    w.exit = 2
    lua.execute('update(0.016)')
    check('Curl warm-up (%d ms, start %.1f ms): done, exit 2' % (start_ms, start_ms) in log() and 'no URL' not in log(),
          'the warm-up is logged with its start time, not its output')
    lua.execute('table.remove(fake.processes, 1); fake.closed = 0')


def google(text, source):
    """The keyless endpoint's reply shape (JSON, non-ASCII escaped like the real one sometimes is)."""
    import json
    return json.dumps([[[text, 'original', None, None, 10]], None, source, None, None, None, 1, []])


def run_translation(check):
    # --- Translation: nothing is started (nothing leaves the game) while Inbound Language is OFF.
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    lua.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.alert"] = false; '
                'fake.values["alomare.better_chat.inbound_language"] = 1')
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    M = lua.globals().BetterChat
    spec = f.specs['alomare.better_chat.inbound_language']
    check(spec.default == 2 and f.specs['alomare.better_chat.outbound_language'].default == 1
          and f.specs['alomare.better_chat.translate_own'].default is False,
          'Inbound Language Automatic, Outbound Language OFF and Inbound Debug off by default')
    check(f.curl_checked == 'C:\\Windows\\system32\\curl.exe' and 'Translation: curl at C:\\Windows\\system32\\curl.exe' in log(),
          "curl.exe is looked for in Windows' system folder only")
    w.add(OTHER, b'hola amigos')
    lua.execute('update(0.25); update(0.016)')
    check(len(f.processes) == 0, 'Inbound Language OFF: no process, nothing sent')

    # On, shown in the chat: one curl per line, the line on its standard input only.
    w.f.on_add_line = lambda sender, text: w.add(int(sender[:-3]), text.encode('utf-8'))
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](3)')  # Game Language
    import re
    target = re.search(r'Text language: (\S+)', log()).group(1)
    tl = {'pt-BR': 'pt', 'zh-Hans': 'zh-CN'}.get(target, target)
    w.add(OTHER, 'hola amigos, ¿qué tal? "extracción" & ya'.encode('utf-8'))
    lua.execute('fake.spawn_cost = 266; update(0.25); fake.spawn_cost = 0')
    check('Slow update: 266.0 ms (chat 0.0, paste 0.0, outbound 0.0, translate 266.0, show 0.0, scale 0.0, other 0.0; '
          'inside them: sound 0.0, curl start 266.0, log ' in log(),
          'a slow curl start is logged as a slow update, in its part')
    finish_warmup(lua, f, log, check, 'in the menu', 266)
    lua.execute('update(0.016)')
    p = f.processes[1] if len(f.processes) == 1 else None
    check(p is not None, 'translation on: a line from another player starts one curl')
    check(p.app == 'C:\\Windows\\system32\\curl.exe' and p.dir == 'C:\\Windows\\system32' and p.cmd == '"C:\\Windows\\system32\\curl.exe" -K -',
          'curl command line: always the same, no address: %r' % (p and p.cmd))
    config = curl_config(p.stdin.data)
    check(config == [('silent', None, ''), ('show-error', None, ''), ('max-time', '8', ''),
                     ('max-filesize', '131072', ''), ('get', None, ''),
                     ('data-urlencode', 'q=hola amigos, ¿qué tal? "extracción" & ya', ''),
                     ('write-out', '\n@@ %{http_code}', ''),
                     ('url', 'https://translate.googleapis.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=' + tl, '')],
          'the request in the config on standard input: the line, the target language from the Text Language: %r'
          % config)
    check(p.flags == 0x08000000 + 0x80000 and f.handle_list and not p.private,
          'no window, a handle list, the child gets only its own pipe ends')
    n_lines = log().count('new chat line(s)')
    lua.execute('update(0.016)')
    check(not any(c.startswith('line ') for c in f.calls.values()), 'nothing shown before curl answers')
    lua.eval('function(s) fake.qpc = fake.qpc + 350 end')(0)
    f.reply(1, google('hi friends, how are you? "extraction" & now', 'es'))
    lua.execute('update(0.016)')
    lines = [c for c in f.calls.values() if c.startswith('line ')]
    check(lines == ['line 10979c0 %x %dULL [ES] hi friends, how are you? "extraction" & now' % (CTX + CHAT, OTHER)],
          'the translation is added through add-line under the same sender: %r' % lines)
    check('Translation 1 (350 ms, start 0.0 ms) es -> %s\n' % tl in log() and 'Translation 1 shown' in log(),
          'the translation is logged with its latency')
    lua.execute('for i = 1, 3 do update(0.25) end')
    check(len(f.processes) == 1 and log().count('new chat line(s)') == n_lines,
          'the added line is not a new message (not translated again, no sound)')
    check(f.closed == 6, 'every handle closed after the reply: %d' % f.closed)

    # Already in the Text Language: not shown. Identical text: not shown.
    w.add(OTHER, b'hello there')
    lua.execute('update(0.25)')
    f.reply(2, google('hello there', tl))
    lua.execute('update(0.016)')
    check('Translation 2 not shown: already in ' + tl in log(), 'a line already in the Text Language is not shown')
    w.add(OTHER, b'roger')
    lua.execute('update(0.25)')
    f.reply(3, google('roger', 'tl' if tl != 'tl' else 'fil'))
    lua.execute('update(0.016)')
    check('Translation 3 not shown: same as the line' in log(), 'a translation equal to the line is not shown')

    # Your own lines: only with Translate My Messages.
    w.add(OWN, b'hola')
    lua.execute('update(0.25); update(0.016)')
    check(len(f.processes) == 3, 'your own line is not translated by default')
    lua.execute('fake.changed["alomare.better_chat.translate_own"](true)')
    w.add(OWN, b'hola')
    lua.execute('update(0.25)')
    check(len(f.processes) == 4, 'Translate My Messages: your own line is translated')
    f.reply(4, google('hello', 'es'))
    lua.execute('update(0.016)')
    lines = [c for c in f.calls.values() if c.startswith('line ')]
    check(lines[-1] == 'line 10979c0 %x %dULL [ES] hello' % (CTX + CHAT, OWN), 'your own translation under your name')
    lua.execute('fake.changed["alomare.better_chat.translate_own"](false)')

    # One curl at a time: the next line waits for the first reply.
    w.add(OTHER, b'primero', push=False)
    w.add(OTHER, b'segundo')
    lua.execute('update(0.25); update(0.016)')
    check(len(f.processes) == 5, 'one curl at a time')
    f.reply(5, google('one', 'es'))
    lua.execute('update(0.016); update(0.016)')
    check(len(f.processes) == 6 and curl_options(f.processes[6])['data-urlencode'] == 'q=segundo',
          'the next line starts after the reply')

    # Errors: an HTTP error and a curl that hangs are logged; nothing is shown.
    shown = len([c for c in f.calls.values() if c.startswith('line ')])
    f.reply(6, 'Not Found', '404')
    lua.execute('update(0.016)')
    check('Translation 6 (0 ms, start 0.0 ms) failed: done, curl exit 0, HTTP 404\n'
          in log() and 'Translation 6 will be retried' not in log(), 'an HTTP error is logged; a 404 is not retried')
    w.add(OTHER, b'tres')
    lua.execute('update(0.25)')
    lua.eval('function(s) fake.qpc = fake.qpc + 13000 end')(0)
    lua.execute('update(0.016)')
    check(f.processes[7].terminated and 'Translation 7 (13000 ms, start 0.0 ms) failed: timeout' in log(),
          'a curl still running after 12 s is ended')
    check(len([c for c in f.calls.values() if c.startswith('line ')]) == shown, 'failures show nothing')

    # Long replies: cut at a character boundary within the game's line.
    w.add(OTHER, b'largo')
    lua.execute('update(0.25)')
    f.reply(8, google('\u6f22' * 300, 'es'))
    lua.execute('update(0.016)')
    last = [c for c in f.calls.values() if c.startswith('line ')][-1]
    text = last.split('ULL ', 1)[1].encode('utf-8')
    check(len(text) <= 0x1f0 and text.startswith(b'[ES] ') and text.endswith('\u6f22'.encode('utf-8')),
          'a long translation is cut to 0x1f0 bytes on a character boundary (%d)' % len(text))

    # The log never holds a message or its translation.
    w.add(OTHER, b'adiosamigos')
    lua.execute('update(0.25)')
    f.reply(9, google('farewellfriends', 'es'))
    lua.execute('update(0.016)')
    check('Translation 9 shown' in log() and not any(t in log() for t in ('adiosamigos', 'farewellfriends', 'hola',
          'segundo', 'Not Found', 'extraction')), 'the log holds no message, translation or reply')

    # A server error: tried once more a second later, then given up.
    w.add(OTHER, b'cinco')
    lua.execute('update(0.25)')
    f.reply(10, 'Server Error', '500')
    lua.execute('update(0.016); update(0.016)')
    check(len(f.processes) == 10 and 'Translation 10 will be retried' in log(), 'a 500 waits a second before the retry')
    lua.eval('function(s) fake.qpc = fake.qpc + 1000 end')(0)
    lua.execute('update(0.016)')
    check(len(f.processes) == 11 and curl_options(f.processes[11])['data-urlencode'] == 'q=cinco',
          'the retry sends the same line')
    f.reply(11, 'Server Error', '500')
    lua.eval('function(s) fake.qpc = fake.qpc + 2000 end')(0)
    lua.execute('update(0.016); update(0.016); update(0.016)')
    check(len(f.processes) == 11 and log().count('Translation 10 will be retried') == 1, 'only one retry')

    # Short lines: ASCII with fewer than 4 letters is not sent (misdetected); any other script is.
    w.add(OTHER, b'ez')
    lua.execute('update(0.25); update(0.016)')
    check(len(f.processes) == 11 and 'Line not translated: too short' in log() and '"ez"' not in log(), 'a short ASCII line is not sent')
    w.add(OTHER, '\u4f60\u597d'.encode('utf-8'))
    lua.execute('update(0.25)')
    check(len(f.processes) == 12, 'a short line in another script is sent')
    f.reply(12, google('hello', 'zh-CN'))
    lua.execute('update(0.016)')

    # Off again: queued lines are dropped, new lines start nothing.
    w.add(OTHER, b'uno', push=False)
    w.add(OTHER, b'dos')
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](1); update(0.25); update(0.016); update(0.016)')
    check(len(f.processes) == 12, 'translation turned off: nothing more is started')
    check(f.closed == 6 * 12, 'every handle of every curl closed: %d' % f.closed)
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](3); update(0.016)')
    w.add(OTHER, b'otra vez')
    lua.execute('update(0.25)')
    check(len(f.processes) == 13 and curl_options(f.processes[13])['data-urlencode'] == 'q=otra vez'
          and log().count('Curl warm-up') == 1,
          'translation on again: no second warm-up, the line starts at once')
    f.reply(13, google('again', 'es'))
    lua.execute('update(0.016)')

    # A line written to end its value and add options to curl's config stays one value.
    for hostile in (b'x" output = "C:\\evil.txt', b'a\\" -o C:\\x \\', b'tab\there\nurl = "http://evil"\r\x7f end\\'):
        w.add(OTHER, hostile)
        lua.execute('update(0.25)')
        q = len(f.processes)
        config = curl_config(f.processes[q].stdin.data)
        names = [c[0] for c in config]
        sent = dict((c[0], c[1]) for c in config)['data-urlencode']
        want = 'q=' + ''.join(' ' if ch < ' ' or ch == '\x7f' else ch for ch in hostile.decode('utf-8'))
        check(names == ['silent', 'show-error', 'max-time', 'max-filesize', 'get', 'data-urlencode', 'write-out', 'url']
              and all(c[2] == '' for c in config) and sent == want,
              'a line with quotes, backslashes or control characters stays one value: %r' % config)
        f.reply(q, google('x', 'es'))
        lua.execute('update(0.016)')

    # Google refuses the endpoint (429, "automated queries"): the line goes again at once to the other endpoint, which
    # stays for the next lines; a line refused by both is given up.
    w.add(OTHER, b'por favor')
    lua.execute('update(0.25)')
    q = len(f.processes)
    check(curl_options(f.processes[q])['url'].startswith('https://translate.googleapis.com/translate_a/t?client=dict-chrome-ex&'),
          'the Chrome extension client first')
    f.reply(q, 'Sorry...', '429')
    lua.execute('update(0.016); update(0.016)')
    check(len(f.processes) == q + 1 and 'Google endpoint dict-chrome-ex refused (HTTP 429): now gtx' in log()
          and curl_options(f.processes[q + 1])['url'] == 'https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=auto&tl=' + tl
          and curl_options(f.processes[q + 1])['data-urlencode'] == 'q=por favor',
          'a 429: the same line at once to the web client (gtx)')
    f.reply(q + 1, google('please', 'es'))
    lua.execute('update(0.016)')
    check('Translation %d shown' % (q + 1) in log() or [c for c in f.calls.values() if c.startswith('line ')][-1].endswith('[ES] please'),
          'its translation is shown')
    w.add(OTHER, b'muchas gracias')
    lua.execute('update(0.25)')
    check(curl_options(f.processes[q + 2])['url'].startswith('https://translate.googleapis.com/translate_a/single?client=gtx&'),
          'the next line goes to the endpoint that answered')
    f.reply(q + 2, 'Forbidden', '403')
    lua.execute('update(0.016); update(0.016)')
    check(len(f.processes) == q + 3 and 'Google endpoint gtx refused (HTTP 403): now dict-chrome-ex' in log(),
          'a 403 switches back')
    f.reply(q + 3, 'Sorry...', '429')
    lua.execute('update(0.016); update(0.016); update(0.016)')
    check(len(f.processes) == q + 3 and 'will be retried' not in log().split('HTTP 403')[-1],
          'refused by both: the line is given up')
    # The Chrome extension client's reply: [["text", "es"]].
    w.add(OTHER, b'buenas noches')
    lua.execute('update(0.25)')
    import json
    f.reply(q + 4, json.dumps([['good night', 'es']]))
    lua.execute('update(0.016)')
    check([c for c in f.calls.values() if c.startswith('line ')][-1].endswith('ULL [ES] good night'),
          "the Chrome extension client's reply shape is read")
    pr = M._test.parse_reply
    check(pr('["Danke"]') is None and pr('[["Danke"]]') == 'Danke', 'a reply without a detected language: the text alone')

    # The JSON reader: escapes, surrogate pairs, nulls, objects.
    js = M._test.json
    v = js('["a\\u00e9\\ud83d\\ude00\\"\\\\", null, -1.5e2, {"k": [true, false]}]')
    check(v[1] == 'a\u00e9\U0001F600"\\' and v[2] is None and v[3] == -150 and v[4]['k'][1] is True,
          'JSON: escapes, surrogate pairs, null, numbers, objects')
    check(not lua.eval('function(s) return (pcall(BetterChat._test.json, s)) end')('[["unterminated'),
          'JSON: bad input raises (caught as a failed reply)')

    # curl.exe missing (Proton, old Windows): translation off, nothing started.
    logdir2 = Path(tempfile.mkdtemp())
    lua2 = new_lua(logdir2)
    w2 = World(lua2)
    lua2.execute('fake.no_curl = true; ModOptionsMenu = fake.menu')
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 5 do update(0.016) end')
    w2.add(OTHER, b'hola')
    lua2.execute('update(0.25); update(0.016)')
    st2 = (logdir2 / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    check('translate off (curl.exe not found in C:\\Windows\\system32)' in st2 and len(w2.f.processes) == 0,
          'no curl.exe: translation off, status says why')

    # The add-line moved away from the chat ring: translations are logged, never shown.
    logdir3 = Path(tempfile.mkdtemp())
    lua3 = new_lua(logdir3)
    World(lua3)
    lua3.globals().fake.patch(0x10979c0, b'\xcc' * 4)
    lua3.execute(SOURCE)
    lua3.execute('for i = 1, 80 do update(0.016) end')
    st3 = (logdir3 / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    check('show off (code not found: add_line (not found))' in st3 and 'translate ready' in st3,
          'add-line not found: only showing is off')


FIELD = 0x14498 + 0x1398                  # the chat's text field in the HUD
FIELD_WIDGET = HUD + FIELD + 0x220        # its text widget
FIELD_TEXT = FIELD + 0x220 + 0x11c        # the field's text (in the HUD block)
INPUT_OPEN = 0x14498 + 0x139b8            # the chat's input-open byte (in the HUD block)


class Chat:
    """The chat's text input as the player uses it: open it, type into the field, press Enter."""

    def __init__(self, lua, w, limit=120):
        self.lua, self.w, self.f = lua, w, w.f
        struct.pack_into('<I', w.hud, FIELD + 0xa84, limit)  # the chat keeps (limit - 1) characters
        self.f.heap(HUD, bytes(w.hud))

    def open(self, is_open=True):
        self.w.hud[INPUT_OPEN] = 1 if is_open else 0
        self.f.heap(HUD, bytes(self.w.hud))
        self.lua.execute('update(0.1)')  # the open flag is read every 100 ms

    def field(self, text):
        """Sets the field's text without a frame (as typing does between two frames)."""
        self.w.hud[FIELD_TEXT:FIELD_TEXT + 0x325] = text.ljust(0x325, b'\0')
        self.f.heap(HUD, bytes(self.w.hud))

    def type(self, text):
        self.field(text)
        self.lua.execute('update(0.016)')

    def enter(self):
        self.f.held[0x0D] = True
        self.lua.execute('update(0.016)')
        self.f.held[0x0D] = None
        self.lua.execute('update(0.016)')

    def say(self, text):
        """Types a message and presses Enter."""
        self.type(text)
        self.enter()


def calls(f, prefix):
    return [c for c in f.calls.values() if c.startswith(prefix)]


def run_outbound(check):
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    chat = Chat(lua, w)
    f.on_send = lambda text: w.add(OWN, text.encode('utf-8'))
    lua.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.alert"] = false; '
                'fake.values["alomare.better_chat.inbound_language"] = 1')
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    status = (logdir / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    send_to = 'send 1097560 %x ' % (CTX + CHAT)
    sends = lambda: [c[len(send_to):] for c in calls(f, 'send ')]
    clears = lambda: [c for c in calls(f, 'text ') if c == 'text %x ' % FIELD_WIDGET]

    def choices(spec):
        return [c() if callable(c) else c for c in (spec.choices[i] for i in range(1, len(spec.choices) + 1))]

    to, sv = (f.specs['alomare.better_chat.' + n] for n in ('outbound_language', 'service'))
    names = choices(to)
    check(to.type == 'choice' and to.label() == 'Outbound Language' and to.default == 1 and names[:2] == ['OFF', 'English']
          and len(names) == 14 and 'Automatic' not in names and 'Translation Service' in to.description()
          and choices(sv) == ['Google Translate', 'Custom']
          and sv.default == 1 and sv.label() == 'Translation Service',
          'Outbound Language (OFF by default, then English first, 13 languages), Translation Service (Google)')
    check('outbound ready' in status, 'outbound ready: the chat send found by its body and its call agree: %r'
          % status.splitlines()[0])

    # Off (default): Enter is not even read; the game sends the message itself.
    chat.open()
    f.key_counts = None
    chat.say(b'hola amigos, cuidado')
    check(not clears() and len(f.processes) == 0 and not (f.key_counts and f.key_counts[0x0D]),
          'Outbound Language OFF: Enter not read, the field left alone, nothing sent anywhere')

    # On: a curl warm-up first (as for inbound), then Enter takes the text and empties the field.
    lua.execute('fake.changed["alomare.better_chat.outbound_language"](2); update(0.016)')  # English
    finish_warmup(lua, f, log, check, 'Outbound Language English')
    chat.open(False)
    f.key_counts = None
    lua.execute('for i = 1, 30 do update(0.016) end')
    check(not (f.key_counts and f.key_counts[0x0D]), 'chat closed: Enter is not read')
    chat.open()
    chat.say(b'hola amigos, cuidado')
    p = f.processes[1] if len(f.processes) == 1 else None
    opts = p and curl_options(p)
    check(len(clears()) == 1 and opts and opts['data-urlencode'] == 'q=hola amigos, cuidado'
          and opts['url'].endswith('&tl=en'),
          'Enter: the field emptied through the game\'s setter, the text sent for translation into English: %r' % opts)
    check('Outbound 1: 20 bytes taken from the field (taken 1, game first 0)' in log(), 'the take is logged by size')
    check(not sends(), 'nothing sent before the translation arrives')
    n_lines = log().count('new chat line(s)')
    f.reply(1, google('hi friends, careful', 'es'))
    lua.execute('update(0.016)')
    check(sends() == ['hi friends, careful'], 'the translation sent through the chat\'s own send: %r' % sends())
    check(log().index('Outbound: first call of the chat send') < log().index('Outbound 1 sent translated (19 bytes)'),
          'a breadcrumb before the first call of the chat send, then the send logged by size')
    lua.execute('for i = 1, 3 do update(0.25) end')
    check(log().count('new chat line(s)') == n_lines, 'the sent line is not a new message (no sound, not translated)')

    # Already in the Outbound Language, a failure, a timeout: the message goes as written.
    chat.say(b'hello everyone here')
    f.reply(2, google('hello everyone here', 'en'))
    lua.execute('update(0.016)')
    check(sends()[-1] == 'hello everyone here' and 'Outbound 2 sent as written (19 bytes, already in en)' in log(),
          'already in English: sent as written')
    chat.say(b'otra cosa mas')
    f.reply(3, 'Not Found', '404')
    lua.execute('update(0.016); update(0.016)')
    check(sends()[-1] == 'otra cosa mas' and 'Outbound 3 will be retried' not in log() and len(f.processes) == 3,
          'translation failed: sent as written at once, no retry')
    chat.say(b'una vez mas')
    lua.eval('function() fake.qpc = fake.qpc + 13000 end')()
    lua.execute('update(0.016)')
    check(f.processes[4].terminated and sends()[-1] == 'una vez mas', 'no answer in 12 s: sent as written')

    # The game ran first: Enter finds the field emptied (the game sent it): logged, nothing taken, nothing sent.
    n_sends, n_proc = len(sends()), len(f.processes)
    chat.type(b'mensaje directo')
    chat.field(b'')
    w.add(OWN, b'mensaje directo')
    chat.enter()
    check('Outbound: Enter found the field already empty (15 bytes the frame before): the game ran first '
          '(game first 1 times, taken 4)' in log() and len(f.processes) == n_proc and len(sends()) == n_sends,
          'the game ran first: logged with the counts, nothing sent twice')
    lua.execute('update(0.25)')
    # Taken, but the game had sent it anyway (the ring shows it): the translation is not sent.
    chat.say(b'carrera rapida')
    w.add(OWN, b'carrera rapida')
    lua.execute('update(0.25)')
    f.reply(len(f.processes), google('quick race', 'es'))
    lua.execute('update(0.016)')
    check('the game sent the message itself (game first 2 times)' in log() and len(sends()) == n_sends
          and 'not sent: the game sent the message itself' in log(), 'taken but sent by the game too: no duplicate')

    # Short lines stay with the game; long translations keep the chat's own character limit (119 here).
    chat.say(b'gg')
    check(len(clears()) == 5 and 'Outbound: left to the game (too short)' in log(), 'a short ASCII line is left to the game')
    chat.say(b'largo mensaje')
    f.reply(len(f.processes), google('x' * 300, 'es'))
    lua.execute('update(0.016)')
    check(sends()[-1] == 'x' * 119, "a long translation is cut to the chat's character limit: %d" % len(sends()[-1]))
    chat.say('你好啊'.encode('utf-8'))
    f.reply(len(f.processes), google('漢' * 300, 'zh-CN'))
    lua.execute('update(0.016)')
    check(sends()[-1] == '漢' * 119, 'characters, not bytes, and within the send\'s 0x200 bytes')

    # A translation the game refuses (nothing reaches the chat) goes as written.
    f.refuse = lambda text: text.startswith('REFUSED')
    chat.say(b'mensaje rechazado')
    f.reply(len(f.processes), google('REFUSED text', 'es'))
    lua.execute('update(0.016)')
    check(sends()[-2:] == ['REFUSED text', 'mensaje rechazado'] and 'sent as written instead' in log(),
          'a translation the game does not take: the message is sent as written')
    f.refuse = None

    # With Translate Inbound on (and your own lines too): outbound goes ahead of waiting lines, and the line it sends
    # is not translated back.
    lua.execute('fake.changed["alomare.better_chat.inbound_language"](3); fake.changed["alomare.better_chat.translate_own"](true)')
    w.add(OTHER, b'hola todos')
    lua.execute('update(0.25)')
    running = len(f.processes)
    w.add(OTHER, b'segunda linea')
    lua.execute('update(0.25)')
    chat.say(b'voy para alla')
    f.reply(running, google('hello all', 'es'))
    lua.execute('update(0.016); update(0.016)')
    nxt = f.processes[running + 1]
    check(curl_options(nxt)['data-urlencode'] == 'q=voy para alla', 'an outbound message goes ahead of waiting lines')
    f.reply(running + 1, google('on my way', 'es'))
    lua.execute('update(0.016); update(0.016)')
    check(sends()[-1] == 'on my way' and curl_options(f.processes[running + 2])['data-urlencode'] == 'q=segunda linea',
          'then the waiting line')
    f.reply(running + 2, google('second line', 'es'))
    lua.execute('for i = 1, 3 do update(0.25) end')
    check(len(f.processes) == running + 2, 'the sent translation is not translated again (Inbound Debug)')

    # Google refuses the endpoint: an outbound message goes again at once to the other one (the player waits).
    chat.say(b'vamos de nuevo')
    q = len(f.processes)
    f.reply(q, 'Sorry...', '429')
    lua.execute('update(0.016); update(0.016)')
    check(len(f.processes) == q + 1 and curl_options(f.processes[q + 1])['data-urlencode'] == 'q=vamos de nuevo'
          and 'gtx' in curl_options(f.processes[q + 1])['url'] and sends()[-1] != 'vamos de nuevo',
          'an outbound message refused with 429: sent again to the other endpoint, not as written')
    f.reply(q + 1, google('here we go again', 'es'))
    lua.execute('update(0.016); update(0.016)')
    check(sends()[-1] == 'here we go again', 'then its translation is sent')

    # Turned off while a message waits: it goes as written at once.
    w.add(OTHER, b'otra linea larga')
    lua.execute('update(0.25)')
    chat.say(b'espera un momento')
    lua.execute('fake.changed["alomare.better_chat.outbound_language"](1); update(0.016)')
    check(sends()[-1] == 'espera un momento' and 'Outbound Language turned OFF' in log(),
          'Outbound Language turned OFF: the waiting message is sent as written')
    f.reply(len(f.processes), google('another long line', 'es'))
    lua.execute('update(0.016)')

    texts = ('hola amigos', 'hi friends', 'otra cosa', 'mensaje directo', 'carrera', 'largo mensaje', 'REFUSED',
             'rechazado', 'voy para', 'on my way', 'espera un', 'vamos de', 'here we go')
    check(not any(t in log() for t in texts), 'the log holds no message or translation')

    # The chat send's code changed: only outbound is off.
    logdir2 = Path(tempfile.mkdtemp())
    lua2 = new_lua(logdir2)
    World(lua2)
    lua2.globals().fake.patch(0x1097560, b'\xcc' * 4)
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 80 do update(0.016) end')
    st2 = (logdir2 / 'BetterChat_STATUS.log').read_text(encoding='utf-8')
    check('outbound off (code not found: send_line (not found))' in st2 and 'translate ready' in st2
          and 'paste ready' in st2, 'chat send not found: only outbound is off')


def chat_completion(content):
    """An OpenAI-compatible chat completions reply."""
    import json
    return json.dumps({'id': 'chatcmpl-1', 'object': 'chat.completion',
                       'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content},
                                    'finish_reason': 'stop'}]})


def run_service(check):
    import json
    logdir = Path(tempfile.mkdtemp())
    lua = new_lua(logdir)
    w = World(lua)
    f = w.f
    chat = Chat(lua, w)
    f.on_send = lambda text: w.add(OWN, text.encode('utf-8'))
    lua.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.alert"] = false; '
                'fake.values["alomare.better_chat.service"] = 2; fake.values["alomare.better_chat.inbound_language"] = 4')
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'BetterChat.log').read_text(encoding='utf-8')
    path = logdir / 'BetterChat_service.json'
    template = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    check(template.get('base_url') == 'https://api.openai.com/v1' and template.get('api_key') == ''
          and template.get('model') == '' and 'Custom service off: BetterChat_service.json was missing' in log()
          and str(logdir) not in log() and 'Logs' not in path.parent.name,
          'Custom without a file: a template is written next to the Logs folder (not in it); the path is not logged')
    examples = template.get('examples', {})
    url_why = lua.globals().BetterChat._test.url_why
    check(examples.get('DeepSeek', {}).get('base_url') == 'https://api.deepseek.com/v1'
          and examples['Qwen, Alibaba Cloud (mainland China)']['base_url'] == 'https://dashscope.aliyuncs.com/compatible-mode/v1'
          and all(url_why(e['base_url']) is False and e['model'] for k, e in examples.items() if k != 'about'),
          'the template lists example services (DeepSeek, Qwen, GLM, OpenAI, local), each a usable address and model')
    finish_warmup(lua, f, log, check, 'saved on, custom service')
    w.add(OTHER, b'hola amigos')
    lua.execute('update(0.25); update(0.016)')
    check(len(f.processes) == 0 and 'Line not translated: custom service BetterChat_service.json was missing' in log(),
          'service not set up: nothing is sent')

    def configure(settings):
        path.write_text(json.dumps(settings, ensure_ascii=False), encoding='utf-8')
        lua.execute('fake.changed["alomare.better_chat.service"](2)')

    configure({'about': 'x', 'base_url': 'https://api.example.com/v1/', 'api_key': 'sk-test-123', 'model': 'gpt-test',
               'glossary': {'Bile Titan': 'Titã da Bile', 'eagle': 'Águia'}})
    check('Custom service ready: api.example.com, model gpt-test\n' in log() and 'sk-test-123' not in log(),
          'the service is read again when applied; the key is never logged')
    line = 'Cuidado com o Bile Titan "agora" \\ ok'
    w.add(OTHER, line.encode('utf-8'))
    lua.execute('update(0.25)')
    p = f.processes[1]
    config = curl_config(p.stdin.data)
    opts = {n: v for n, v, _ in config}
    headers = [v for n, v, _ in config if n == 'header']
    body = json.loads(opts['data-raw'])
    system = body['messages'][0]['content']
    check([c[0] for c in config] == ['silent', 'show-error', 'max-time', 'max-filesize', 'header', 'header',
                                     'data-raw', 'write-out', 'url']
          and all(c[2] == '' for c in config) and opts['max-time'] == '15'
          and opts['url'] == 'https://api.example.com/v1/chat/completions'
          and headers == ['Content-Type: application/json', 'Authorization: Bearer sk-test-123'],
          'a POST to base_url/chat/completions, the key in a header, all in the config on standard input: %r'
          % [c[0] for c in config])
    check(body['model'] == 'gpt-test' and body['messages'][0]['role'] == 'system'
          and body['messages'][1] == {'role': 'user', 'content': line} and set(body) == {'model', 'messages'},
          'the body is valid JSON: the model, the prompt, the line as written (quotes and backslash); no temperature')
    check('into English' in system and '{language}' not in system and 'Bile Titan = Titã da Bile' in system
          and 'eagle' not in system, 'the prompt names the Inbound Language; only the glossary terms the line has')
    f.reply(1, chat_completion('[pt] Watch out for the Bile Titan "now"'))
    lua.execute('update(0.016)')
    lines = calls(f, 'line ')
    check(lines[-1:] == ['line 10979c0 %x %dULL [PT] Watch out for the Bile Titan "now"' % (CTX + CHAT, OTHER)]
          and 'Translation 1 (0 ms, start 0.0 ms) pt -> en' in log(),
          'the reply\'s language code becomes the label, as with Google: %r' % lines[-1:])

    def answer(text, reply, status='200'):
        w.add(OTHER, text)
        lua.execute('update(0.25)')
        f.reply(len(f.processes), reply, status)
        lua.execute('update(0.016)')

    answer(b'hello there friends', chat_completion('[en] hello there friends'))
    check('Translation 2 not shown: already in en' in log(), 'a line already in the language is not shown')
    answer(b'bonjour a tous', chat_completion('<think>French, easy.</think> "hello everyone"'))
    check(calls(f, 'line ')[-1].endswith('ULL hello everyone'), 'reasoning and quotes left out; no code: no label')
    answer(b'otra linea aqui', json.dumps({'error': {'message': 'Incorrect API key provided: sk-test-123 (otra linea)',
                                                     'type': 'invalid_request_error', 'code': 'invalid_api_key'}}), '401')
    check('failed: done, curl exit 0, HTTP 401, invalid_request_error\n' in log() and 'Incorrect' not in log()
          and 'sk-test-123' not in log(), "an API error: its type logged, never its message")
    answer(b'cuarta linea', chat_completion(''))
    check('failed: empty translation' in log(), 'an empty reply is a failure')

    # Outbound with the custom service: the Outbound Language in the prompt, and a longer wait (18 s).
    lua.execute('fake.changed["alomare.better_chat.outbound_language"](3)')
    chat.open()
    chat.say(b'vamos a extraer')
    p = f.processes[len(f.processes)]
    body = json.loads(curl_options(p)['data-raw'])
    check('into German' in body['messages'][0]['content'] and body['messages'][1]['content'] == 'vamos a extraer',
          'outbound with the custom service: translated into the Outbound Language (Deutsch)')
    lua.eval('function() fake.qpc = fake.qpc + 13000 end')()
    lua.execute('update(0.016)')
    check(not p.terminated, 'the custom service gets more than 12 s')
    lua.eval('function() fake.qpc = fake.qpc + 6000 end')()
    lua.execute('update(0.016)')
    check(p.terminated and calls(f, 'send ')[-1].endswith(' vamos a extraer'), 'no answer in 18 s: sent as written')

    # A service on this PC: http to localhost, no key, its own prompt.
    configure({'base_url': 'http://localhost:11434/v1', 'model': 'qwen3:8b',
               'prompt': 'Translate to {language}. Answer [code] translation.'})
    check('Custom service ready: localhost:11434, model qwen3:8b, no key' in log(), 'a local service without a key')
    answer(b'otra mas por favor', chat_completion('[es] one more please'))
    p = f.processes[len(f.processes)]
    config = curl_config(p.stdin.data)
    body = json.loads({n: v for n, v, _ in config}['data-raw'])
    check([v for n, v, _ in config if n == 'header'] == ['Content-Type: application/json']
          and body['messages'][0]['content'] == 'Translate to English. Answer [code] translation.',
          'no key: no Authorization header; the player\'s own prompt with the language')

    # The game's names: into Chinese the English terms a line mentions get their official Chinese name (the longest
    # term, not the one inside it; the player's glossary first); into English the Chinese ones get the English name.
    configure({'base_url': 'https://api.example.com/v1', 'api_key': 'k', 'model': 'm', 'glossary': {'Hulk': 'Hulk'}})
    lua.execute('fake.changed["alomare.better_chat.outbound_language"](13)')  # 简体中文 (OFF first)
    chat.say(b'eagle 500kg bomb on the heavy devastators and that hulk, then extraction')
    p = f.processes[len(f.processes)]
    system = json.loads(curl_options(p)['data-raw'])['messages'][0]['content']
    check('into Simplified Chinese' in system and 'Eagle 500kg Bomb = \u201c\u98de\u9e70\u201d500kg\u70b8\u5f39' in system
          and 'Heavy Devastator = \u91cd\u578b\u8e42\u8e8f\u8005' in system and 'Devastator = \u8e42' not in system
          and 'Hulk = Hulk' in system and 'Hulk = \u5de8' not in system and 'Extraction = \u64a4\u79bb' in system,
          'into Chinese: the official names of the terms the line mentions: %r' % system.split('\n')[-1])
    f.reply(len(f.processes), chat_completion('[en] x'))
    lua.execute('update(0.016); update(0.016)')
    lua.execute('fake.changed["alomare.better_chat.outbound_language"](1)')
    answer('\u5c0f\u5fc3\u5410\u9178\u6cf0\u5766'.encode('utf-8'), chat_completion('[zh] watch out'))  # 小心吐酸泰坦
    system = json.loads(curl_options(f.processes[len(f.processes)])['data-raw'])['messages'][0]['content']
    check('\u5410\u9178\u6cf0\u5766 = Bile Titan' in system, 'into English: a Chinese name gets its English name')
    t = lua.globals().BetterChat._test
    check(t.mentions('two chargers here', 'charger') and t.mentions('charger!', 'charger') and t.mentions('the hulks', 'hulk')
          and not t.mentions('a discharger', 'charger') and not t.mentions('hulking', 'hulk')
          and not t.mentions('spearhead', 'spear'), 'English terms match as whole words (or their plural)')
    found = t.game_terms('Call the Orbital Laser on the Bile Titan', 'zh-TW')
    check([found[i]['from'] for i in (1, 2)] == ['Orbital Laser', 'Bile Titan']
          and found[2]['to'] == '\u95ca\u6b65\u87f2', 'Traditional Chinese: the names the game shows its players')
    check(len(t.game_terms('hola', 'de')) == 0, 'other languages: no game terms')

    # Files that can't be used: the reason is logged and nothing is sent.
    bad = [({'base_url': 'http://example.com/v1', 'model': 'm'}, 'base_url must start with https://'),
           ({'base_url': 'https://api.example.com', 'model': ''}, 'model is empty'),
           ({'base_url': 'https://api.example.com', 'model': 'm', 'prompt': 'Translate this.'}, 'prompt has no {language}'),
           ({'base_url': 'https://api.example.com', 'model': 'm', 'api_key': 'a"b'}, 'api_key has quotes'),
           ({'base_url': 'https://api.example.com', 'model': 'm', 'glossary': ['a']}, 'a glossary entry'),
           ({'base_url': 'https://api.example.com', 'model': 'm', 'prompt': 'x' * 3000 + '{language}'}, 'prompt is longer')]
    for settings, why in bad:
        configure(settings)
        check('Custom service off: ' + why in log(), 'not used: ' + why)
    path.write_text('{"base_url": ', encoding='utf-8')
    lua.execute('fake.changed["alomare.better_chat.service"](2)')
    check('Custom service off: the file is not valid JSON' in log(), 'not valid JSON: not used')
    n = len(f.processes)
    answer(b'esto no se envia', '')
    check(len(f.processes) == n, 'an unusable service sends nothing')
    ok_urls = ['https://api.openai.com/v1', 'http://localhost:1234/v1', 'http://127.0.0.1:8080', 'http://[::1]:11434/v1']
    bad_urls = ['http://192.168.0.2/v1', 'http://localhost.evil.com/v1', 'ftp://x', 'https://a b', 'https://x"y']
    check(all(url_why(u) is False for u in ok_urls) and all(url_why(u) for u in bad_urls),
          'https anywhere, http only to this PC: %r' % [(u, url_why(u)) for u in ok_urls + bad_urls])
    jt = lua.globals().BetterChat._test.json_text
    check(json.loads(jt('a"b\\c\n\td\x01')) == 'a"b\\c\n\td\x01', 'JSON text: quotes, backslashes, control characters')


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
