# Better Chat

A Helldivers 2 text-chat quality-of-life mod that runs on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader).

Makes the in-game chat better: sound alerts for new messages, a resizable chat box, Ctrl+V paste, translations of other players' messages, and translating your own messages so only the translation is sent to the squad.

## Features

- **Sound Alert in Ship / Sound Alert in Mission:** when another player sends a chat message, one of the game's own sounds plays, at most once every 2 seconds. Ship and mission can each use a different sound; there is also an option to play the alert for your own messages.
- **Chat Size:** adjustable from 50% to 200%.
- **Paste (Ctrl+V):** pastes the clipboard text while you type, turning line breaks into spaces and leaving out emoji.
- **Translate Chat:** translates other players' messages into your language and shows the translation below the original; only you can see it.
- **Translation Service:** Google Translate (default) or a custom OpenAI-compatible service.
- **Outbound Translation (translation only):** when on, your outgoing message is intercepted and translated, and only the translation is sent to the squad. If translation fails, your original is sent instead, so no message is lost. Translate Chat must also be on.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Optional: install [Mod Options Menu](https://www.nexusmods.com/helldivers2/mods/16625) for the settings.
3. Import the ZIP with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy, keeping Bingus Shared Loader last in the load order (so it loads first).

## Settings

Settings are in Mod Options Menu: Escape menu → MODS → Better Chat.

Without Mod Options Menu, only the "Player Joined" sound is on by default; everything else keeps the game's default behavior.

## Languages

The game's HUD language is set by the in-game Text Language option (up to 15 languages). This mod's setting labels follow it and ship translations for:

English, German, Spanish, Latin American Spanish, French, Italian, Japanese, Korean, Polish, Brazilian Portuguese, Portuguese, Russian, Simplified Chinese, Traditional Chinese.

For the few game languages not listed above, the settings fall back to English.

## Translation and privacy

- Inbound translations are visible only to you; they are never sent to other players.
- Only the message text is sent to the translation service; no player names or other game data.
- Nothing is sent while translation is off.
- Outbound translation sends your message text to the chosen service first, then sends the translation to the squad.

## Configuring an OpenAI-compatible service

After choosing "Custom (OpenAI-compatible)" in Translation Service, edit this file:

`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BetterChat.custom.json`

The first time the custom service is used, this file is created automatically as a template. Fill in `api_key`, then pick and apply Translation Service again in the game to reload it. It looks like this:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-your-key",
  "model": "gpt-4o-mini",
  "prompt": "",
  "glossary": {}
}
```

- `base_url`: any OpenAI-compatible Chat Completions address; the mod calls `base_url/chat/completions`. Examples: OpenAI `https://api.openai.com/v1`, DeepSeek `https://api.deepseek.com/v1`, or a local server.
- `api_key`: the provider's key. It lives only in this file and is sent only to `base_url`.
- `model`: the model name, e.g. `gpt-4o-mini`.
- `prompt` (optional): a custom system prompt; `{language}` becomes the target language name (inbound uses Translate To, outbound uses Outbound Language). Leave it empty to use the mod's built-in prompt.
- `glossary` (optional): extra term mappings.

Only the message text is sent to the chosen service; nothing is sent while the service is off.

## Notes

- Google Translate uses a free public endpoint that may be rate-limited or change; a failed translation does not affect the chat itself.
- Translation needs the curl.exe that ships with Windows; it is unavailable on Steam Deck (Proton) or Linux.
- With "Custom (OpenAI-compatible)", inbound and outbound translations have no automatic source-language detection like Google's — the direction is decided entirely by the `prompt` in `BetterChat.custom.json`. The mod only replaces `{language}` with the target language name; if the `prompt` has no `{language}`, the direction is fixed by the prompt itself.
- Outbound translation is new in V7: the logic is verified offline, but whether the intercept always wins the race against the game's own send should still be confirmed once in game.

## License

GPL-3.0 or later. `src/bingus_text.lua` is CowboyBingus's, under the Zero-Clause BSD license.
