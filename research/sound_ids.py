"""Game sound ids the game's code plays on a source of their own (no position): every call to the UI sound function
(0x1327f50, `play(_, id)`) and to post_audio (0x12982d0, `post(_, id)`) with the id loaded into edx just before.

  python -B mods/BetterChat/research/sound_ids.py <out.json>

Writes {id hex: [call site rvas]} per function. Needs the decrypted dump (tools/sigtool.py) and capstone.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))

from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_REG_EDX, X86_REG_RDX  # noqa: E402

from callsto import calls_to  # noqa: E402
from sigtool import Image  # noqa: E402

FUNCTIONS = {'ui_sound': 0x1327f50, 'post_audio': 0x12982d0}


def ids_for(img, target):
    out = {}
    for rva, kind in calls_to(img, target):
        if kind != 'call':
            continue
        for j in reversed(list(img.dis(img.back(rva, 8), 9))):
            if j.address >= rva:
                continue
            ops = j.operands
            if len(ops) == 2 and ops[0].type == X86_OP_REG and ops[0].reg in (X86_REG_EDX, X86_REG_RDX):
                if j.mnemonic == 'mov' and ops[1].type == X86_OP_IMM:
                    out.setdefault('%08x' % (ops[1].imm & 0xffffffff), []).append(rva)
                break  # edx set some other way
    return out


def main():
    img = Image()
    result = {name: ids_for(img, rva) for name, rva in FUNCTIONS.items()}
    for name, ids in result.items():
        print(name, len(ids), 'ids')
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
