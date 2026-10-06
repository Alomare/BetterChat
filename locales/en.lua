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
        -- The sound of confirming a popup in the menus.
        ['choice.confirm'] = 'Menu Confirm',
        -- The sound of going back in the menus.
        ['choice.back'] = 'Menu Back',
        -- The sound of opening the action wheel (the radial menu of emotes and quick messages).
        ['choice.wheel'] = 'Action Wheel',
        -- The sound of buying an item (a loud one).
        ['choice.purchase'] = 'Item Purchase',
        -- The sound of a confirmation dialog (a loud one).
        ['choice.dialog'] = 'Confirmation Dialog',
        -- A slider: the text chat box's size in percent (100 = the game's size).
        ['option.scale.label'] = 'Chat Size (%)',
        ['option.scale.description'] = 'Makes the text chat and its text bigger or smaller. 100 keeps the game\'s size.',
        -- A toggle: translates other players' chat messages into the language chosen in Translate To.
        ['option.translate.label'] = 'Translate Chat',
        ['option.translate.description'] = 'Sends each message from another player to Google Translate (translate.googleapis.com) and adds the translation to your chat when it is in another language than the one set in Translate To. Only you see it. Nothing is sent while this is off.',
        -- A choice: the language translations are shown in.
        ['option.translate_to.label'] = 'Translate To',
        ['option.translate_to.description'] = 'The language translations are shown in. Messages already in it are not translated. Automatic: the language of your Windows regional format (Settings > Time & language > Language & region). Game Language: the game\'s Text Language.',
        -- The choices, shown in upper case: the language of Windows' regional format, and the game's Text Language setting.
        ['choice.automatic'] = 'Automatic',
        ['choice.game'] = 'Game Language',
        -- A toggle: also translates the player's own messages.
        ['option.translate_own.label'] = 'Translate My Messages',
        ['option.translate_own.description'] = 'Also translates your own messages, so you can try translation alone. Only you see the translations.',
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
        ['choice.confirm'] = 48,
        ['choice.back'] = 48,
        ['choice.wheel'] = 48,
        ['choice.purchase'] = 48,
        ['choice.dialog'] = 48,
        ['option.scale.label'] = 64,
        ['option.scale.description'] = 400,
        ['option.translate.label'] = 64,
        ['option.translate.description'] = 400,
        ['option.translate_to.label'] = 64,
        ['option.translate_to.description'] = 400,
        ['choice.automatic'] = 48,
        ['choice.game'] = 48,
        ['option.translate_own.label'] = 64,
        ['option.translate_own.description'] = 400,
    },
}
