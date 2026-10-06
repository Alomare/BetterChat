"""Survey of the game's sounds that Better Chat could play as a new message alert.

The game plays a sound by its own 32-bit hash; the game data resource (type 0xe3f2851035957af5, name
0xb9ee36888ef19818: u32 capacity, then capacity x (game hash, Wwise event id), empty key 0) maps it to a Wwise
event (lookup 0x12556e0, loaded by 0x1255800). For every mapped event in the chosen sound banks, this script
follows the event's Play actions down to the sounds, sums the volume property (id 5 in these banks, dB) of each
sound and its parents, decodes the audio and measures it. Ids the game's code passes to its UI sound function or
to post_audio (sound_ids.py) are marked: those are known to be played on a source of their own.

  python -B mods/BetterChat/research/sound_survey.py <sound_ids.json> <out dir> [--banks a,b,...] [--wav N]

Banks default to game_init, ui_ship and ui_mission (bank names without content/audio/). Writes survey.json and
survey.tsv, ranked by score = the loudest 100 ms of the audio (RMS, dBFS) + the volume properties; bus volumes are
not included. With --wav, the N loudest events that last 3 s at most are written as WAV files to listen to. Needs
HD2ReAudio's core (the game reader and its audio index), hd2-audio-modder's v154 hierarchy parser, vgmstream-cli
and numpy.
"""
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
AUDIO = Path(os.environ.get('HD2_AUDIO_TOOLS') or ROOT.parent / 'Audio')  # HD2ReAudio and hd2-audio-modder
sys.path.insert(0, str(AUDIO / 'HD2ReAudio' / 'core'))
sys.path.insert(0, str(AUDIO / '_examples' / 'hd2-audio-modder'))

import wwise_hierarchy_154 as wh  # noqa: E402
from audiodiver.index import AudioIndex  # noqa: E402 (the core package; it was named reaudio before)
from audiodiver.wem import VGMSTREAM  # noqa: E402

MAP_TYPE, MAP_NAME = 0xe3f2851035957af5, 0xb9ee36888ef19818
PROP_VOLUME = 0x05
SOURCE_PLUGIN = 2   # plugin id low nibble: a generated source (the events' second sound: controller haptics)
BANKS = 'game_init,ui_ship,ui_mission'
PLAY = 0x0403


def sound_map(ix):
    """{game hash: Wwise event id} from the game data."""
    for name in ix.game.packages:
        try:
            toc = ix.game.package_toc(name) or []
        except Exception:  # noqa: BLE001 (not an archive)
            continue
        for fid, tid, _off, _size in toc:
            if fid == MAP_NAME and tid == MAP_TYPE:
                data = ix.game.resource(name, fid, tid)[0]
                n = struct.unpack_from('<I', data)[0]
                pairs = struct.unpack_from('<%dI' % (2 * n), data, 4)
                return {pairs[i]: pairs[i + 1] for i in range(0, 2 * n, 2) if pairs[i]}
    raise SystemExit('sound map resource not found')


def bank_name(dep):
    m = re.search(rb'[\x20-\x7e]{6,}', dep or b'')
    return m.group().decode() if m else None


def hirc_events(raw):
    """Event ids in a bank without parsing it (light scan of the HIRC chunk)."""
    off = 0
    while off + 8 <= len(raw):
        tag, size = raw[off:off + 4], struct.unpack_from('<I', raw, off + 4)[0]
        if tag == b'HIRC':
            h, out, p = raw[off + 8:off + 8 + size], set(), 4
            for _ in range(struct.unpack_from('<I', h)[0]):
                t, sz, oid = h[p], *struct.unpack_from('<II', h, p + 1)
                if t == 4:
                    out.add(oid)
                p += 5 + sz
            return out, h
        off += 8 + size
    return set(), None


def props(entry):
    bp = getattr(entry, 'baseParam', None)
    if bp is None:
        return {}
    return {pid: struct.unpack('<f', bytes(v))[0] for pid, v in zip(bp.propBundle.pIDs, bp.propBundle.pValues)}


def positioning(entry):
    """(overrides parent, 3D) from the entry's positioning bits."""
    bp = getattr(entry, 'baseParam', None)
    if bp is None or not bp.positioningParamData:
        return False, False
    bits = bp.positioningParamData[0]
    return bool(bits & 1), bool(bits & 1 and bits & 2)


def chain(h, entry):
    out, seen = [], set()
    while entry is not None and entry.get_id() not in seen:
        seen.add(entry.get_id())
        out.append(entry)
        pid = entry.get_parent_id()
        entry = h.entries.get(pid) if pid else None
    return out


def describe_sound(h, sound):
    links = chain(h, sound)
    volume, is_3d, decided, bus = 0.0, False, False, 0
    for e in links:
        p = props(e)
        volume += p.get(PROP_VOLUME, 0.0)
        override, three_d = positioning(e)
        if not decided and override:
            is_3d, decided = three_d, True
        if not bus and getattr(e, 'baseParam', None) is not None and e.baseParam.overrideBusId:
            bus = e.baseParam.overrideBusId
    src = sound.sources[0]
    return {'sound': sound.get_id(), 'source': src.source_id, 'stream': src.stream_type, 'plugin': src.plugin_id,
            'volume_db': round(volume, 2), '3d': is_3d, 'positioning_known': decided, 'bus': bus,
            'parents': len(links) - 1}


def sounds_under(h, oid, depth=0, seen=None):
    seen = seen if seen is not None else set()
    e = h.entries.get(oid)
    if e is None or oid in seen or depth > 8:
        return []
    seen.add(oid)
    if isinstance(e, wh.Sound):
        return [e]
    kids = getattr(getattr(e, 'children', None), 'children', None) or []
    out = []
    for k in kids:
        out += sounds_under(h, k, depth + 1, seen)
    return out


def measure(ix, sid, keep=None):
    """Peak, loudest 100 ms (RMS, dBFS) and duration of a source's audio; keep = a path to save the WAV."""
    try:
        data = ix.wem(sid)
    except KeyError:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        wem, wav = Path(tmp) / 'a.wem', Path(tmp) / 'a.wav'
        wem.write_bytes(data)
        r = subprocess.run([VGMSTREAM, '-o', str(wav), str(wem)], capture_output=True)
        if r.returncode or not wav.exists():
            return None
        with wave.open(str(wav)) as w:
            rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
            pcm = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float64) / 32768
        if keep:
            Path(keep).write_bytes(wav.read_bytes())
    pcm = pcm.reshape(-1, ch).mean(axis=1) if ch > 1 else pcm
    if len(pcm) == 0:
        return None
    win = max(1, rate // 10)
    sq = np.convolve(pcm ** 2, np.ones(win) / win, mode='valid') if len(pcm) >= win else np.array([np.mean(pcm ** 2)])
    db = lambda v: round(20 * math.log10(max(v, 1e-9)), 1)  # noqa: E731
    return {'peak_dbfs': db(np.max(np.abs(pcm))), 'loud100_dbfs': db(math.sqrt(np.max(sq))),
            'rms_dbfs': db(math.sqrt(np.mean(pcm ** 2))), 'seconds': round(len(pcm) / rate, 2), 'channels': ch}


def main():
    ids_file, out = Path(sys.argv[1]), Path(sys.argv[2])
    wav_count = int(sys.argv[sys.argv.index('--wav') + 1]) if '--wav' in sys.argv else 0
    banks = (sys.argv[sys.argv.index('--banks') + 1] if '--banks' in sys.argv else BANKS).split(',')
    banks = {'content/audio/' + b for b in banks}
    out.mkdir(parents=True, exist_ok=True)
    harvested = json.loads(ids_file.read_text())
    ix = AudioIndex(log=lambda m: print(m, file=sys.stderr))
    smap = sound_map(ix)
    print('sound map:', len(smap), 'entries', file=sys.stderr)
    game_ids = {}  # Wwise event -> game hashes
    for gid, ev in smap.items():
        game_ids.setdefault(ev, []).append(gid)
    played = {}  # game hash -> {function: call sites}
    for func, ids in harvested.items():
        for hid, sites in ids.items():
            played.setdefault(int(hid, 16), {})[func] = ['0x%x' % s for s in sites]
    rows = {}
    for bid in sorted(ix.banks):
        raw, dep = ix.bank_files(bid)
        name = bank_name(dep) or '%016x' % bid
        if name not in banks:
            continue
        ev_ids, h_raw = hirc_events(raw)
        h = wh.WwiseHierarchy_154()
        h.load(h_raw)
        for ev in sorted(ev_ids & set(game_ids)):
            acts, sounds = [], []
            for aid in h.entries[ev].ulActionIDs:
                a = h.entries.get(aid)
                if a is None:
                    continue
                acts.append('0x%04x 0x%08x' % (a.ulActionType, a.idExt))
                if a.ulActionType == PLAY:
                    sounds += [describe_sound(h, s) for s in sounds_under(h, a.idExt)]
            w = rows.setdefault(ev, {'game_ids': ['0x%08x' % g for g in game_ids[ev]], 'event': ev, 'banks': [],
                                     'actions': acts, 'sounds': {},
                                     'played_by': {k: v for g in game_ids[ev] for k, v in played.get(g, {}).items()}})
            w['banks'].append(name.rsplit('/', 1)[-1])
            for s in sounds:
                if s['plugin'] & 0xf != SOURCE_PLUGIN:
                    w['sounds'].setdefault(s['sound'], s)
    measured = {}
    for w in rows.values():
        w['sounds'] = list(w['sounds'].values())
        for s in w['sounds']:
            if s['source'] not in measured:
                measured[s['source']] = measure(ix, s['source'])
            m = measured[s['source']]
            s.update(m or {'audio': 'unreadable'})
            if m:
                s['score'] = round(m['loud100_dbfs'] + s['volume_db'], 1)
        scored = [s for s in w['sounds'] if 'score' in s]
        w['score'] = max((s['score'] for s in scored), default=None)
        w['score_min'] = min((s['score'] for s in scored), default=None)
        w['seconds'] = max((s['seconds'] for s in scored), default=None)
        w['buses'] = sorted({s['bus'] for s in w['sounds']})
    rows = sorted(rows.values(), key=lambda w: -(w['score'] if w['score'] is not None else -999))
    (out / 'survey.json').write_text(json.dumps(rows, indent=1))
    with open(out / 'survey.tsv', 'w', encoding='utf-8') as f:
        f.write('score\tmin\tseconds\tgame id\tevent\tbanks\tsounds\tbuses\tplayed by\n')
        for w in rows:
            f.write('%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n' % (
                w['score'], w['score_min'], w['seconds'], ','.join(w['game_ids']), w['event'], ','.join(w['banks']),
                len(w['sounds']), ','.join(map(str, w['buses'])),
                ' '.join('%s:%s' % (k, ','.join(v)) for k, v in w['played_by'].items())))
    if wav_count:
        wavs = out / 'wav'
        wavs.mkdir(exist_ok=True)
        picked = [w for w in rows if w['score'] is not None and w['seconds'] <= 3][:wav_count]
        for rank, w in enumerate(picked, 1):
            best = max((s for s in w['sounds'] if 'score' in s), key=lambda s: s['score'])
            measure(ix, best['source'], wavs / ('%02d_%s_%+.0f.wav' % (rank, w['game_ids'][0], w['score'])))
    print('events:', len(rows), 'scored:', sum(1 for w in rows if w['score'] is not None), file=sys.stderr)


if __name__ == '__main__':
    main()
