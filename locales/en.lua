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
        -- A slider: the text chat box's size in percent (100 = the game's size).
        ['option.scale.label'] = 'Chat Size (%)',
        ['option.scale.description'] = 'Makes the text chat and its text bigger or smaller. 100 keeps the game\'s size.',
        -- A toggle: a sound plays when another player sends a chat message (the sounds are picked in the next two options).
        ['option.alert.label'] = 'Sound Alert',
        ['option.alert.description'] = 'Plays one of the game\'s own sounds when another player sends a chat message, at most once every 2 seconds. Pick the sounds for the ship and for missions below.',
        -- Two choices: the sound played when another player sends a chat message, on the ship and in missions.
        ['option.alert_ship.label'] = 'Sound Alert in Ship',
        ['option.alert_ship.description'] = 'Plays one of the game\'s own sounds when another player sends a chat message while you are on the ship, at most once every 2 seconds. Pick a sound and apply to hear it.',
        ['option.alert_mission.label'] = 'Sound Alert in Mission',
        ['option.alert_mission.description'] = 'Plays one of the game\'s own sounds when another player sends a chat message while you are in a mission, at most once every 2 seconds. Pick a sound and apply to hear it.',
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
        -- The sound played when a dead player asks to be reinforced (missions only).
        ['choice.reinforce'] = 'Reinforce Request',
        -- The countdown tick played when a player leaves the mission area (missions only).
        ['choice.countdown'] = 'Countdown',
        -- A choice: which service translates (both directions).
        ['option.service.label'] = 'Translation Service',
        ['option.service.description'] = 'Who translates, both ways. Google Translate: free, no account (translate.googleapis.com). Custom: an OpenAI-compatible service you set in BetterChat_service.json, next to the Logs folder in %LOCALAPPDATA%\\CowboyBingus\\Helldivers2 (created the first time). Only the message text is sent.',
        -- The choices, shown in upper case: Google's free translation, and a service the player sets up.
        ['choice.google'] = 'Google Translate',
        ['choice.custom'] = 'Custom',
        -- A choice: the language other players' messages (inbound) are translated into, or OFF (the game's own word,
        -- shown in the game's language: write "off" as your game shows it in the description).
        ['option.inbound_language.label'] = 'Inbound Language',
        ['option.inbound_language.description'] = 'Translates other players\' messages into this language: each message goes to the Translation Service, and its translation is added to your chat when it is in another language. Only you see it. Automatic: the language of your Windows regional format. Game Language: the game\'s Text Language. OFF: nothing is sent.',
        -- The choices, shown in upper case: the language of Windows' regional format, and the game's Text Language setting.
        ['choice.automatic'] = 'Automatic',
        ['choice.game'] = 'Game Language',
        -- A choice: the language the player's own messages (outbound) are sent in, or OFF; the squad sees only the translation.
        ['option.outbound_language.label'] = 'Outbound Language',
        ['option.outbound_language.description'] = 'Sends your messages translated into this language: when you press Enter, your message goes to the Translation Service first and the squad sees only the translation, about a second later. If translation fails or your message is already in that language, it goes as you wrote it. OFF: nothing is sent.',
        -- A toggle: inbound translation also translates the player's own messages (shown only to them, to test it alone).
        ['option.translate_own.label'] = 'Inbound Debug',
        ['option.translate_own.description'] = 'Inbound Language also translates your own messages, so you can test it alone. Only you see these translations.',
    },
    -- Mod Options Menu's limits, in characters.
    limits = {
        ['option.mod'] = 40,
        ['option.scale.label'] = 64,
        ['option.scale.description'] = 400,
        ['option.alert.label'] = 64,
        ['option.alert.description'] = 400,
        ['option.alert_ship.label'] = 64,
        ['option.alert_ship.description'] = 400,
        ['option.alert_mission.label'] = 64,
        ['option.alert_mission.description'] = 400,
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
        ['choice.reinforce'] = 48,
        ['choice.countdown'] = 48,
        ['option.service.label'] = 64,
        ['option.service.description'] = 400,
        ['choice.google'] = 48,
        ['choice.custom'] = 48,
        ['option.inbound_language.label'] = 64,
        ['option.inbound_language.description'] = 400,
        ['choice.automatic'] = 48,
        ['choice.game'] = 48,
        ['option.outbound_language.label'] = 64,
        ['option.outbound_language.description'] = 400,
        ['option.translate_own.label'] = 64,
        ['option.translate_own.description'] = 400,
    },
}
