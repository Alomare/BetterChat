"""Offline test of Better Chat's outbound translation under LuaJIT, without the game.dll dump.

The game.dll image is fabricated from the mod's own SIGS table (read out of better_chat.lua), so the real signature
engine runs against it: a minimal PE header, a code section and a data section, and each signature's fixed bytes at
its known RVA with the field values encoded into the wildcard bytes. The network context (chat ring) and the HUD
(chat input) live on a sparse fake heap; kernel32/user32 and curl are stubs. This exercises the real intercept ->
translate -> send-only-translation path, plus the race guard and the failure fallback.

Run from the mod folder:  python -B tests/test_outbound_intercept.py
"""
import struct
import sys
from pathlib import Path

from lupa.luajit21 import LuaRuntime

MOD = Path(__file__).resolve().parent.parent
SOURCE_PATH = MOD / 'better_chat.lua'

BASE = 0x40000000
CTX, HUD, STATE = 0x20000000, 0x30000000, 0x60000000
CONTEXT_G, GAME_STATE_G, HUD_G = 0x2000000, 0x2000100, 0x2000200   # data-section RVAs
OWN = 0x1111222233334444

MEM = {}  # sparse byte memory: address -> byte


def mem_write(addr, data):
    for i, b in enumerate(data):
        MEM[addr + i] = b


def mem_read(addr, size):
    return bytes(MEM.get(addr + i, 0) for i in range(size))


def fake_read(addr, size):
    return mem_read(int(addr), int(size))


def fake_write(addr, data):
    mem_write(int(addr), data)


# Field values written into the signature bytes. `context`, `game_state` and `hud` are globals in the data section
# that hold a pointer to the matching fake heap object; `call`/`rip` values are RVAs.
FIELD_VALUES = {
    'context': CONTEXT_G, 'game_state': GAME_STATE_G, 'hud': HUD_G,
    'send_fn': 0x1097560, 'ui_sound': 0x1327f50, 'field_update': 0x18f2dc0, 'set_text_call': 0x143dd60,
    'chat': 0xc418, 'local_peer': 0xb398, 'ring_first': 0x9590, 'ring_count': 0x9594, 'line_stride': 0x228,
    'line_sender': 0xb98, 'line_time': 0xb90, 'line_text': 0xba0, 'hud_active': 0x24e335, 'chat_hud': 0x14498,
    'mode': 0xac21c, 'join_mission': 0x82250982, 'join_ship': 0xda653421, 'leave_mission': 0x3cf15e0,
    'leave_ship': 0xc386a64a, 'tab_hover': 0x78e15850, 'tab_click': 0xadd37058, 'button_hover': 0x65e34ad8,
    'button_click': 0x468c8e58, 'option_click': 0x144418d5, 'option_refused': 0x3e8c63db, 'chat_open': 0x139b8,
    'chat_field': 0x1398, 'field_max': 0xa84, 'field_widget': 0x220, 'text_limit': 0x324, 'widget_text': 0x11c,
    'send_sound': 0xe1ba68c0,
}


def extract_sigs():
    """Evaluates the mod's SIGS table with LuaJIT and serializes it to plain lines."""
    src = Path(SOURCE_PATH).read_text(encoding='utf-8')
    start = src.index('local SIGS = ')
    open_brace = src.index('{', start)
    depth = 0
    for i in range(open_brace, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                close = i + 1
                break
    table_text = src[open_brace:close]
    serializer = r'''
local out = {}
for i, s in ipairs(SIGS) do
    local fields = {}
    for fn, f in pairs(s.fields or {}) do
        local offs, nexts = {}, {}
        for _, o in ipairs(f[2] or {}) do offs[#offs + 1] = tostring(o) end
        for _, o in ipairs(f[3] or {}) do nexts[#nexts + 1] = tostring(o) end
        fields[#fields + 1] = fn .. ':' .. f[1] .. ':' .. table.concat(offs, ',') .. ':' .. table.concat(nexts, ',')
    end
    table.sort(fields)
    out[#out + 1] = table.concat({s.name, s.rva, s.text, table.concat(fields, ';')}, '|')
end
return table.concat(out, '\n')
'''
    rt = LuaRuntime(unpack_returned_tuples=True, encoding=None)
    text = rt.execute('local SIGS = ' + table_text + '\n' + serializer)
    sigs = []
    for line in text.decode('utf-8').splitlines():
        name, rva, sigtext, fields = line.split('|')
        fields = [f for f in fields.split(';') if f]
        parsed_fields = []
        for f in fields:
            fn, kind, offs, nexts = f.split(':')
            offs = [int(x) for x in offs.split(',') if x]
            nexts = [int(x) for x in nexts.split(',') if x]
            parsed_fields.append((fn, kind, offs, nexts))
        sigs.append({'name': name, 'rva': int(rva), 'text': sigtext, 'fields': parsed_fields})
    return sigs


def build_game_dll(sigs):
    # Minimal PE header: MZ, PE, two sections (executable .text, non-executable .data).
    mem_write(BASE + 0, b'MZ')
    mem_write(BASE + 0x3c, struct.pack('<I', 0x40))
    nt = bytearray(0x18)
    nt[0:4] = b'PE\x00\x00'
    struct.pack_into('<H', nt, 6, 2)       # NumberOfSections
    struct.pack_into('<H', nt, 20, 0xF0)   # SizeOfOptionalHeader
    mem_write(BASE + 0x40, bytes(nt))
    sections = bytearray(2 * 40)
    struct.pack_into('<I', sections, 0 * 40 + 8, 0x2000000)  # .text size (code RVAs reach ~0x18f0000)
    struct.pack_into('<I', sections, 0 * 40 + 12, 0x1000)    # .text rva
    struct.pack_into('<I', sections, 0 * 40 + 36, 0x60000020)  # code | execute | read
    struct.pack_into('<I', sections, 1 * 40 + 8, 0x1000000)  # .data size
    struct.pack_into('<I', sections, 1 * 40 + 12, 0x2000000) # .data rva
    struct.pack_into('<I', sections, 1 * 40 + 36, 0xC0000040)  # read | write
    mem_write(BASE + 0x40 + 24 + 0xF0, bytes(sections))

    # Each signature's fixed bytes at its RVA; wildcard bytes are zero unless they are a field value.
    for sig in sigs:
        tokens = sig['text'].split()
        raw = bytearray(len(tokens))
        for i, tok in enumerate(tokens):
            raw[i] = int(tok, 16) if tok != '??' else 0
        for fn, kind, offs, nexts in sig['fields']:
            value = FIELD_VALUES[fn]
            for k, off in enumerate(offs):
                if kind in ('rip', 'call'):
                    nxt = nexts[k]
                    disp = (value - (sig['rva'] + nxt)) & 0xFFFFFFFF
                    struct.pack_into('<I', raw, off, disp)
                elif kind == 'u32':
                    struct.pack_into('<I', raw, off, value)
                else:
                    raw[off] = value & 0xFF
        mem_write(BASE + sig['rva'], bytes(raw))

    # The globals the rip fields point at, each holding a fake heap pointer.
    mem_write(BASE + CONTEXT_G, struct.pack('<Q', CTX))
    mem_write(BASE + GAME_STATE_G, struct.pack('<Q', STATE))
    mem_write(BASE + HUD_G, struct.pack('<Q', HUD))


def build_heap():
    chat = CTX + 0xc418
    mem_write(CTX + 0xb398, struct.pack('<Q', OWN))
    mem_write(chat + 0, b'\x01')                     # text chat enabled
    mem_write(chat + 0x9590, struct.pack('<II', 0, 0))  # ring first, count

    widget = HUD + 0x14498
    field = widget + 0x1398
    text_widget = field + 0x220
    mem_write(widget + 0x139b8, b'\x01')             # chat input open
    mem_write(field + 0xa84, struct.pack('<I', 0x100))
    mem_write(text_widget + 0x11c, b'\x00' * 0x324)

    mem_write(STATE + 0xac21c, struct.pack('<I', 3))  # game mode: ship


def set_field_text(text):
    widget = HUD + 0x14498
    field = widget + 0x1398
    text_widget = field + 0x220
    mem_write(text_widget + 0x11c, text.encode('utf-8') + b'\x00')


def get_field_text():
    widget = HUD + 0x14498
    field = widget + 0x1398
    text_widget = field + 0x220
    data = mem_read(text_widget + 0x11c, 0x324)
    return data.split(b'\x00', 1)[0].decode('utf-8', 'replace')


PRELUDE = r'''
local real_ffi = require('ffi')
fake = {
    sent = 0, last_send = '', calls = {}, enter = false, source = 'zh-CN', reply_mode = 'ok',
    translate_text = function(text) return 'HELLO' end, qpc = 0, handle = 1000, job = nil,
    log = '',
}
CowboyBingusModLoader = {
    api = 1, version = 17, log_directory = 'C:\\fake\\logs',
    open_log = function(name)
        return { write = function(self, s) fake.log = fake.log .. s end, flush = function() end }
    end,
}

local function wstr(buf, s)
    for i = 1, #s do buf[i - 1] = s:byte(i) end
    return #s
end

local k32 = {}
k32.better_chat_GetCurrentProcess = function() return real_ffi.cast('void *', 0x1234) end
k32.better_chat_GetCurrentProcessId = function() return 4242 end
k32.better_chat_GetModuleHandleA = function(name)
    if name == 'game.dll' then return real_ffi.cast('void *', %BASE%) end
    return nil
end
k32.better_chat_ReadProcessMemory = function(process, address, buffer, size, done)
    local b = fake_read(tonumber(real_ffi.cast('uintptr_t', address)), size)
    if not b or #b ~= size then done[0] = 0; return 0 end
    real_ffi.copy(buffer, b, size)
    done[0] = size
    return 1
end
k32.better_chat_GetSystemDirectoryW = function(buf, size) return wstr(buf, 'C:\\fake') end
k32.better_chat_GetFileAttributesW = function(path) return 0x20 end
k32.better_chat_QueryPerformanceFrequency = function(freq) freq[0] = 10000000; return 1 end
k32.better_chat_QueryPerformanceCounter = function(count)
    fake.qpc = fake.qpc + 1; count[0] = fake.qpc * 100000; return 1
end
k32.better_chat_GetLastError = function() return 0 end
k32.better_chat_GetUserDefaultLocaleName = function(name, size) return wstr(name, 'en-US') end
k32.better_chat_LCIDToLocaleName = function(lcid, name, size, flags) return wstr(name, 'en-US') end
k32.better_chat_GetUserDefaultUILanguage = function() return 0x0409 end
k32.better_chat_CreatePipe = function(read, write, sa, size)
    fake.handle = fake.handle + 1; read[0] = real_ffi.cast('void *', fake.handle)
    fake.handle = fake.handle + 1; write[0] = real_ffi.cast('void *', fake.handle)
    return 1
end
k32.better_chat_SetHandleInformation = function(handle, mask, flags) return 1 end
k32.better_chat_InitializeProcThreadAttributeList = function(list, count, flags, size) size[0] = 0; return 0 end
k32.better_chat_UpdateProcThreadAttribute = function(...) return 1 end
k32.better_chat_DeleteProcThreadAttributeList = function(list) return 1 end
k32.better_chat_CreateProcessW = function(app, cmdline, pa, ta, inherit, flags, env, dir, si, info)
    fake.job = { config = '', reply = '' }
    info.hProcess = real_ffi.cast('void *', 5555)
    info.hThread = real_ffi.cast('void *', 5556)
    info.dwProcessId, info.dwThreadId = 5555, 5556
    return 1
end
k32.better_chat_WriteFile = function(handle, data, size, done, overlapped)
    fake.job.config = real_ffi.string(data, size)
    local q = fake.job.config:match('data%-urlencode = "q=([^"]*)"') or ''
    if fake.reply_mode == 'fail' then
        fake.job.reply = 'curl: (7) failed\n@@ 400'
    else
        local translated = fake.translate_text(q)
        fake.job.reply = string.format('[[["%s","%s",null,null,1]],null,"%s"]\n@@ 200',
                                       translated, q, fake.source)
    end
    done[0] = size
    return 1
end
k32.better_chat_PeekNamedPipe = function(pipe, buffer, size, read, available, left)
    available[0] = #(fake.job and fake.job.reply or '')
    return 1
end
k32.better_chat_ReadFile = function(handle, buffer, size, done, overlapped)
    local reply = fake.job and fake.job.reply or ''
    if #reply == 0 then done[0] = 0; return 0 end
    real_ffi.copy(buffer, reply, #reply)
    done[0] = #reply
    fake.job.reply = ''
    return 1
end
k32.better_chat_WaitForSingleObject = function(handle, milliseconds) return 0 end
k32.better_chat_GetExitCodeProcess = function(process, code) code[0] = 0; return 1 end
k32.better_chat_TerminateProcess = function(process, code) return 1 end
k32.better_chat_CloseHandle = function(handle) return 1 end
k32.better_chat_GlobalLock = function(memory) return real_ffi.cast('void *', 0x9000) end
k32.better_chat_GlobalUnlock = function(memory) return 1 end
k32.better_chat_GlobalSize = function(memory) return 0 end

local user32 = {}
user32.better_chat_GetForegroundWindow = function() return real_ffi.cast('void *', 7000) end
user32.better_chat_GetWindowThreadProcessId = function(window, pid) pid[0] = 4242; return 1 end
user32.better_chat_GetAsyncKeyState = function(key)
    if key == 0x0D then return fake.enter and -32768 or 0 end
    return 0
end
user32.better_chat_OpenClipboard = function(owner) return 1 end
user32.better_chat_CloseClipboard = function() return 1 end
user32.better_chat_GetClipboardData = function(format) return nil end

package.loaded.ffi = setmetatable({
    load = function(name)
        if name == 'kernel32' then return k32 end
        if name == 'user32' then return user32 end
        error('unexpected library ' .. tostring(name))
    end,
    cast = function(t, v)
        if t == 'BetterChatSend' then
            return function(chat, unused, text)
                fake.sent = fake.sent + 1
                fake.last_send = tostring(text)
                fake.calls[#fake.calls + 1] = 'send:' .. tostring(text)
                return nil
            end
        end
        if t == 'BetterChatSetText' then
            return function(widget, text)
                fake.calls[#fake.calls + 1] = 'settext:' .. tostring(text)
                fake_write(widget + 0x11c, text .. '\0')
                return 1
            end
        end
        if t == 'BetterChatAddLine' then
            return function(chat, sender, text)
                fake.calls[#fake.calls + 1] = 'line:' .. tostring(text)
                return nil
            end
        end
        if t == 'BetterChatSound' then return function(unused, id) return nil end end
        if t == 'BetterChatSetVec' then return function(widget, value) return nil end end
        return real_ffi.cast(t, v)
    end
}, {__index = real_ffi})

local function run_lua(src)
    return assert(loadstring(src))()
end
mod_text = {
    module = run_lua(bingus_text_src),
    locales = {
        en = run_lua(en_src),
        bundled = { ['zh-Hans'] = run_lua(zh_hans_src), ['zh-Hant'] = run_lua(zh_hant_src) },
    },
}
os.getenv = function(name)
    if name == 'LOCALAPPDATA' then return %LOCALAPPDATA% end
    return nil
end
'''


def new_lua():
    sigs = extract_sigs()
    build_game_dll(sigs)
    build_heap()
    rt = LuaRuntime(unpack_returned_tuples=True, encoding=None)
    rt.globals().fake_read = fake_read
    rt.globals().fake_write = fake_write
    rt.globals().bingus_text_src = (MOD / 'src' / 'bingus_text.lua').read_bytes()
    rt.globals().en_src = (MOD / 'locales' / 'en.lua').read_bytes()
    rt.globals().zh_hans_src = (MOD / 'locales' / 'zh-Hans.lua').read_bytes()
    rt.globals().zh_hant_src = (MOD / 'locales' / 'zh-Hant.lua').read_bytes()
    prelude = PRELUDE.replace('%BASE%', str(BASE)).replace('%LOCALAPPDATA%', repr(str(Path.home() / '.codex-test-logs')))
    rt.execute(prelude.encode('utf-8'))
    rt.execute(SOURCE_PATH.read_bytes())
    return rt


def lua(rt, expr):
    return rt.execute(('return ' + expr).encode('utf-8'))


def do(rt, code):
    rt.execute(code.encode('utf-8'))


def drive(rt, frames, dt=0.016):
    for _ in range(frames):
        rt.execute(('update(%f)' % dt).encode('utf-8'))


def prepare_outbound(rt, text='你好'):
    do(rt, "BetterChat._test.options().translate = true")
    do(rt, "BetterChat._test.options().broadcast = true")
    do(rt, "BetterChat._test.options().broadcast_to = 2")   # English
    do(rt, "BetterChat._test.options().translate_service = 1")
    set_field_text(text)


def enter_edge(rt, down):
    do(rt, 'fake.enter = %s' % ('true' if down else 'false'))


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    return bool(cond)


def dump_state(rt):
    expr = ('(function() local o={}; o[#o+1]="ready="..tostring(BetterChat.ready); '
            'o[#o+1]="retired="..tostring(BetterChat.retired); '
            'o[#o+1]="errors="..tostring(BetterChat.errors); '
            'local f=BetterChat._test.features(); for k,v in pairs(f) do o[#o+1]=k.."="..tostring(v) end; '
            'return table.concat(o,", ") end)()')
    return lua(rt, expr).decode('utf-8', 'replace') + '\n' + lua(rt, 'fake.log').decode('utf-8', 'replace')[-2000:]


def case_happy(rt):
    ok = []
    prepare_outbound(rt)
    enter_edge(rt, False)
    drive(rt, 3)
    ready = lua(rt, 'BetterChat.ready') is True
    ok.append(check('ready', ready, 'mod became ready'))
    if not ready:
        print('  state:', dump_state(rt))
    ok.append(check('send feature', lua(rt, "BetterChat._test.features().send") is True, 'send resolved from chat_send'))
    ok.append(check('paste feature', lua(rt, "BetterChat._test.features().paste") is True, 'field access resolved'))

    enter_edge(rt, True)
    drive(rt, 1)
    enter_edge(rt, False)
    ok.append(check('field cleared', get_field_text() == '', 'original removed from the input'))
    ok.append(check('pending set', lua(rt, 'BetterChat._test.outbound.pending ~= nil'), 'intercept pending'))
    ok.append(check('nothing sent yet', lua(rt, 'fake.sent') == 0, 'send waits for the translation'))

    drive(rt, 12)
    ok.append(check('translation sent', lua(rt, 'fake.last_send') == b'HELLO', 'only the translation is sent'))
    ok.append(check('single send', lua(rt, 'fake.sent') == 1, 'no duplicate'))
    ok.append(check('pending cleared', lua(rt, 'BetterChat._test.outbound.pending == nil'), 'intercept finished'))
    return all(ok)


def case_race(rt):
    ok = []
    prepare_outbound(rt)
    enter_edge(rt, False)
    drive(rt, 3)
    enter_edge(rt, True)
    drive(rt, 1)
    enter_edge(rt, False)
    # Simulate the game having sent the original before the field was cleared: put it in the ring.
    chat = CTX + 0xc418
    mem_write(chat + 0xb98, struct.pack('<Q', OWN))
    mem_write(chat + 0xba0, '你好'.encode('utf-8') + b'\x00')
    mem_write(chat + 0x9590, struct.pack('<II', 0, 1))
    drive(rt, 12)
    ok.append(check('race cancels send', lua(rt, 'fake.sent') == 0, 'original already sent, no duplicate translation'))
    return all(ok)


def case_fallback(rt):
    ok = []
    prepare_outbound(rt)
    do(rt, "fake.reply_mode = 'fail'")
    enter_edge(rt, False)
    drive(rt, 3)
    enter_edge(rt, True)
    drive(rt, 1)
    enter_edge(rt, False)
    drive(rt, 12)
    ok.append(check('fallback sends original', lua(rt, 'fake.last_send') == '你好'.encode('utf-8'),
                    'translation failed, original is sent instead'))
    ok.append(check('single send', lua(rt, 'fake.sent') == 1, 'no duplicate'))
    return all(ok)


def main():
    failures = 0
    for name, case in (('happy path', case_happy), ('race guard', case_race), ('fallback', case_fallback)):
        print('=== %s ===' % name)
        try:
            if not case(new_lua()):
                failures += 1
        except Exception as exc:
            print('ERROR', repr(exc))
            failures += 1
    print()
    print('RESULT:', 'OK' if failures == 0 else 'FAIL')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
