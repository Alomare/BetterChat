"""Better Chat's game terms (RESEARCH.md, "Custom service"): the game's own English, Simplified Chinese and Traditional
Chinese names for words players use in chat, read from the game's localized strings and written into better_chat.lua
between the GLOSSARY markers. The custom service gets the ones a line mentions in its prompt, so that a language
model writes the names Chinese players see in their game (and the English names for Chinese ones).

The strings come from a dump of the game's `strings` resources (one TSV row per string id, a column per language code;
the game's Simplified Chinese code is cn), written by FileDiver's strings_dump tool:
  go run ./cmd/strings_dump "<game>/data" ../../_research/strings/strings_<build>.tsv   (from _shared/filediver)

Usage (from the workspace root): python -B mods/BetterChat/research/glossary.py [--check]
  --check   only verify that the script's block is current (exit 1 otherwise)
Credit: spkel-max's PR #2 proposed a built-in English -> Simplified Chinese glossary for the custom service.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
ROOT = MOD.parents[1]
SCRIPT = MOD / 'better_chat.lua'
BUILD = 25480438
STRINGS = ROOT / '_research' / 'strings' / ('strings_%d.tsv' % BUILD)
BEGIN = '-- BEGIN GLOSSARY'
END = '-- END GLOSSARY'

# The terms, by group: the English name as the game writes it (a plural is matched by the mod).
TERMS = [
    # The war.
    'Helldiver', 'Super Earth', 'Super Destroyer', 'Terminid', 'Automaton', 'Illuminate', 'SEAF', 'Hellpod',
    'Hellbomb', 'Requisition Slips', 'Medal', 'Super Credits', 'Common Samples', 'Rare Samples', 'Super Sample',
    'Galactic War', 'Major Order', 'Warbond', 'Super Citizen', 'Democracy Officer', 'Malevelon Creek',
    # Terminids.
    'Scavenger', 'Hunter', 'Warrior', 'Hive Guard', 'Brood Commander', 'Bile Spewer', 'Nursing Spewer', 'Bile Warrior',
    'Stalker', 'Charger', 'Charger Behemoth', 'Spore Charger', 'Bile Titan', 'Impaler', 'Shrieker', 'Pouncer',
    'Alpha Commander', 'Dragonroach', 'Hive Lord', 'Predator Hunter', 'Rupture Warrior', 'Rupture Charger',
    'Spore Spewer', 'Bug Hole',
    # Automatons.
    'Trooper', 'Raider', 'Marauder', 'Devastator', 'Heavy Devastator', 'Rocket Devastator', 'Berserker', 'Commissar',
    'Scout Strider', 'Hulk', 'Hulk Bruiser', 'Hulk Scorcher', 'Hulk Obliterator', 'Annihilator Tank', 'Shredder Tank',
    'Barrager Tank', 'Factory Strider', 'Gunship', 'Dropship', 'Cannon Turret', 'Detector Tower', 'Fabricator',
    'War Strider', 'Incineration Corps', 'Jet Brigade',
    # Illuminate.
    'Overseer', 'Elevated Overseer', 'Crescent Overseer', 'Watcher', 'Voteless', 'Harvester', 'Fleshmob', 'Stingray',
    'Leviathan',
    # Stratagems.
    'Reinforce', 'Resupply', 'SOS Beacon', 'Eagle Airstrike', 'Eagle 500kg Bomb', 'Eagle Cluster Bomb',
    'Eagle Napalm Airstrike', 'Eagle Strafing Run', 'Eagle 110mm Rocket Pods', 'Eagle Smoke Strike', 'Eagle Rearm',
    'Orbital Laser', 'Orbital Railcannon Strike', 'Orbital Precision Strike', 'Orbital Gas Strike', 'Orbital EMS Strike',
    'Orbital Smoke Strike', 'Orbital Airburst Strike', 'Orbital 120mm HE Barrage', 'Orbital 380mm HE Barrage',
    'Orbital Walking Barrage', 'Orbital Napalm Barrage', 'Shield Generator Pack', 'Jump Pack', 'Supply Pack',
    'Guard Dog', 'Autocannon', 'Recoilless Rifle', 'Quasar Cannon', 'Expendable Anti-Tank', 'Spear', 'Railgun',
    'Machine Gun', 'Heavy Machine Gun', 'Flamethrower', 'Grenade Launcher', 'Laser Cannon', 'Arc Thrower',
    'Anti-Materiel Rifle', 'Stalwart', 'Airburst Rocket Launcher', 'Commando', 'Mortar Sentry', 'Autocannon Sentry',
    'Rocket Sentry', 'Gatling Sentry', 'Machine Gun Sentry', 'EMS Mortar Sentry', 'Tesla Tower',
    'Anti-Personnel Minefield', 'Shield Generator Relay', 'HMG Emplacement', 'Patriot Exosuit', 'Emancipator Exosuit',
    # Weapons.
    'Liberator', 'Breaker', 'Slugger', 'Punisher', 'Sickle', 'Scorcher', 'Dominator', 'Eruptor', 'Exploding Crossbow',
    'Purifier', 'Blitzer', 'Diligence', 'Defender', 'Senator', 'Redeemer', 'Verdict', 'Peacemaker', 'Grenade Pistol',
    # Objectives.
    'Extraction', 'Stratagem Jammer', 'Illegal Broadcast', 'Geological Survey', 'Launch ICBM', 'SSSD',
]

# A term with several names in the strings: the one the game uses for it in chat-relevant places (cn).
PICK = {'Warrior': '武斗虫', 'Spear': '飞矛', 'Stalwart': '盟友', 'Defender': '捍卫者'}
# A term only inside longer strings: the string it is taken from and the part that names it.
INSIDE = {
    'Super Destroyer': ('CALL IN SUPER DESTROYER', '超级驱逐舰', '超級驅逐艦'),
    'Warbond': ('WARBONDS', '战争债券', '戰爭債券'),
    'Incineration Corps': ('THE INCINERATION CORPS', '炽灼部队', '焚燒軍團'),
    'Jet Brigade': ('THE JET BRIGADE', '喷气旅', '噴射隊'),
    'Illegal Broadcast': ('TERMINATE ILLEGAL BROADCAST', '非法广播', '非法廣播'),
    'Geological Survey': ('CONDUCT GEOLOGICAL SURVEY', '地质调查', '地質調查'),
}
QUOTES = [('“', '”'), ('「', '」'), ('"', '"')]


def unquote(s):
    for a, b in QUOTES:
        if s.startswith(a) and s.endswith(b) and s.count(a) == 1:
            return s[len(a):-len(b)]
    return s


def load():
    rows = []
    with open(STRINGS, encoding='utf-8', newline='') as f:
        r = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        head = next(r)
        us, cn, tc = head.index('us'), head.index('cn'), head.index('tc')
        for row in r:
            if len(row) > tc and row[us]:
                rows.append((row[us].strip(), row[cn].strip(), row[tc].strip()))
    return rows


def terms(rows):
    out, problems = [], []
    for term in TERMS:
        if term in INSIDE:
            source, cn, tc = INSIDE[term]
            if not any(r[0] == source and cn in r[1] and tc in r[2] for r in rows):
                problems.append('%s: %r no longer holds %s / %s' % (term, source, cn, tc))
            out.append((term, cn, tc))
            continue
        exact = [r for r in rows if r[0] == term and r[1]] or [r for r in rows if r[0].lower() == term.lower() and r[1]]
        if PICK.get(term):
            exact = [r for r in exact if unquote(r[1]) == PICK[term]]
        forms = Counter((unquote(r[1]), unquote(r[2]) or unquote(r[1])) for r in exact)
        if not forms:
            problems.append('%s: not in the strings' % term)
            continue
        if len({f[0] for f in forms}) > 1:
            problems.append('%s: several names %r (add it to PICK)' % (term, sorted(forms)))
            continue
        cn, tc = forms.most_common(1)[0][0]
        out.append((term, cn, tc))
    for i in (1, 2):
        seen = {}
        for t in out:
            if t[i] in seen and t[i] != t[0]:
                problems.append('%s and %s share the name %s' % (seen[t[i]], t[0], t[i]))
            seen.setdefault(t[i], t[0])
    return out, problems


def lua_string(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"


def block(entries):
    lines = [BEGIN + ' (generated by research/glossary.py from the game\'s strings, build %d)' % BUILD,
             'local GAME_TERMS = {']
    for en, cn, tc in entries:
        lines.append('    {%s, %s, %s},' % (lua_string(en), lua_string(cn), lua_string(tc)))
    lines += ['}', END]
    return '\n'.join(lines)


def main():
    check = '--check' in sys.argv
    entries, problems = terms(load())
    for p in problems:
        print('PROBLEM', p)
    text = SCRIPT.read_text(encoding='utf-8')
    a, b = text.index(BEGIN), text.index(END) + len(END)
    new = text[:a] + block(entries) + text[b:]
    if check:
        ok = new == text and not problems
        print('glossary: %d terms, %s' % (len(entries), 'current' if ok else 'NOT current'))
        return 0 if ok else 1
    if problems:
        return 1
    SCRIPT.write_text(new, encoding='utf-8', newline='')
    print('glossary: %d terms written' % len(entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
