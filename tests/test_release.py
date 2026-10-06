"""Offline test of Better Chat under LuaJIT, with the real game.dll code as fake process memory.

The Ghidra-ready dump (_research/game_25480438.dll, offsets == RVAs) is mapped at a fake base, so the signatures and
the values read from the matched code are checked against the game's own code. The network context (chat ring) and the
HUD (chat widget) are simulated on a fake heap; the game's UI sound, its widget scale setter and Mod Options Menu are
stubs that record their calls. Kernel32 offers only reads: the mod writes no game memory itself.

Run from the workspace root or the mod folder:  python -B mods/BetterChat/tests/test_release.py
"""
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
CowboyBingusModLoader = {api = 1, open_log = function(name)
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
local function floats(v) return string.format('%.3f,%.3f', v.x, v.y) end
package.loaded.ffi = setmetatable({
    load = function(name) assert(name == 'kernel32', 'unexpected library ' .. name); return k32 end,
    cast = function(t, v)
        if t == 'BetterChatSound' then
            local rva = tonumber(v) - BASE
            return function(unused, id) fake.calls[#fake.calls + 1] = string.format('sound %x %x', rva, id) end
        end
        if t == 'BetterChatSetVec' then
            local rva = tonumber(v) - BASE
            return function(widget, value)
                fake.calls[#fake.calls + 1] = string.format('vec %x %x %s', rva, widget, floats(value))
                write_mem(widget + 0x14, ffi.string(ffi.new('float[2]', value.x, value.y), 8))
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

    # --- Without Mod Options Menu: the defaults (sound: player joined notice).
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
    check('Ready: chat = context + 0xc418, ring at +0x9590 (stride 0x228, sender +0xb98); sound ready, scale ready; '
          'sounds: joined 0xda653421/0x82250982, left 0xc386a64a/0x03cf15e0, '
          'tab 0xadd37058/0xadd37058, subtab 0x468c8e58/0x468c8e58, option 0x144418d5/0x144418d5' in log(),
          'offsets and every sound id from code, every feature ready')
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
    check(list(f.calls.values())[-1] == 'sound 1327f50 %x' % JOIN_MISSION, 'in missions: the mission join notice')
    # A cleared history (count back to 0): new baseline, no sound.
    n = len(f.calls)
    w.first = w.count = 0
    struct.pack_into('<II', w.ctx, CHAT + 0x9590, 0, 0)
    w.push_ctx()
    lua.execute('update(3.0)')
    check(len(f.calls) == n and 'first 0, count 0' in log(), 'a cleared history is a new baseline')
    # The default leaves the size alone.
    check('Chat scale' not in log(), 'default: chat size untouched')

    # --- Mod Options Menu: two options, texts as functions, values applied.
    logdir2 = Path(tempfile.mkdtemp())
    lua2 = new_lua(logdir2)
    w2 = World(lua2)
    f2 = w2.f
    lua2.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.sound"] = 1')
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 5 do update(0.016) end')
    log2 = lambda: (logdir2 / 'BetterChat.log').read_text(encoding='utf-8')
    order = f2.order.split()
    s = f2.specs
    sound = s['alomare.better_chat.sound']
    check(order == ['alomare.better_chat.' + n for n in ('sound', 'scale')],
          'options registered in order: %r' % order)
    names = [sound.choices[i]() for i in range(2, 7)]
    check(sound.type == 'choice' and sound.choices[1] == 'OFF'
          and names == ['Player Joined', 'Player Left', 'Menu Tab', 'Menu Subtab', 'Option Click']
          and sound.default == 2 and sound.label() == 'New Message Sound' and sound.mod() == 'Better Chat'
          and sound.mod_id == 'alomare.better_chat', 'sound choice: OFF + five game sounds, texts as functions')
    sc = s['alomare.better_chat.scale']
    check(sc.type == 'slider' and sc.min == 50 and sc.max == 200 and sc.step == 5 and sc.default == 100
          and not sc.gap          and sc.label() == 'Chat Size (%)', 'size slider: 50-200% in steps of 5, 100 by default')
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(len(f2.calls) == 0 and '1 new chat line(s), 1 from other players' in log2(), 'sound OFF: no sound')
    for choice, want, what in ((4, TAB, 'menu tab'), (5, SUBTAB, 'menu subtab'), (6, OPTION, 'option click')):
        f2.calls = lua2.table()
        lua2.execute('fake.changed["alomare.better_chat.sound"](%d)' % choice)
        check(list(f2.calls.values()) == ['sound 1327f50 %x' % want], 'picking %s plays it once (preview)' % what)
    lua2.execute('update(3.0)')
    f2.calls = lua2.table()
    w2.add(OTHER)
    lua2.execute('update(0.25)')
    check(list(f2.calls.values()) == ['sound 1327f50 %x' % OPTION], 'the picked sound plays for new messages')
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
    s3 = lua3.globals().fake.specs['alomare.better_chat.sound']
    check(s3.label == 'New Message Sound' and s3.choices[4] == 'Menu Tab', 'v1.0: texts as strings')

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
    lua6.execute('ModOptionsMenu = fake.menu; fake.values["alomare.better_chat.sound"] = 4')
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

    print('%d/%d' % (sum(ok), len(ok)))
    return all(ok)


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
