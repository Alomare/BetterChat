-- Better Chat: English texts, the source of every translation.
-- Translators: see TRANSLATING.md in Mod Options Menu's repository (the same files and tool work for this mod).
-- Every text shows in Mod Options Menu (escape menu > MODS), which upper-cases the mod name and the choices.
return {
    mod = 'better_chat',
    title = 'Better Chat',
    language = 'en',
    strings = {
        -- The mod's name: its category button in Mod Options Menu (escape menu > MODS), shown in upper case.
        ['option.mod'] = 'Better Chat',
        -- A choice: the sound played when another player sends a chat message (or OFF).
        ['option.sound.label'] = 'New Message Sound',
        ['option.sound.description'] = 'Plays one of the game\'s own sounds when another player sends a chat message, at most once every 2 seconds. Pick a sound and apply to hear it.',
        -- The choices, shown in upper case: game sounds named by where the game plays them. The notice when a player joins.
        ['choice.joined'] = 'Player Joined',
        -- The notice when a player leaves.
        ['choice.left'] = 'Player Left',
        -- The sound of clicking a tab in the menus.
        ['choice.tab'] = 'Menu Tab',
        -- The sound of clicking a subtab (a category inside a tab) in the menus.
        ['choice.subtab'] = 'Menu Subtab',
        -- The sound of clicking an option (changing a setting) in the menus.
        ['choice.option'] = 'Option Click',
        -- A slider: the text chat box's size in percent (100 = the game's size).
        ['option.scale.label'] = 'Chat Size (%)',
        ['option.scale.description'] = 'Makes the text chat and its text bigger or smaller. 100 keeps the game\'s size.',
    },
    -- Mod Options Menu's limits, in characters.
    limits = {
        ['option.mod'] = 40,
        ['option.sound.label'] = 64,
        ['option.sound.description'] = 400,
        ['choice.joined'] = 48,
        ['choice.left'] = 48,
        ['choice.tab'] = 48,
        ['choice.subtab'] = 48,
        ['choice.option'] = 48,
        ['option.scale.label'] = 64,
        ['option.scale.description'] = 400,
    },
}
