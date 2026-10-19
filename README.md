<img width="1920" height="1080" alt="thumbnail" src="https://github.com/user-attachments/assets/a3a2c8f7-4444-43fd-bce7-505fe5d0d2ee" />

# Better Chat

A Helldivers 2 Lua mod for [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) that plays a sound when another player sends a chat message, lets you resize the text chat, adds Ctrl+V paste to the chat, and can translate the chat both ways, through Google Translate or your own AI translation service.

## Features

- **Chat Size (%):** from 50 to 200% (default 100), makes the text chat and its text bigger or smaller.
- **Sound Alert in Ship / Sound Alert in Mission:** when another player's chat message arrives, one of the game's own sounds plays, at most once every 2 seconds, chosen separately for the ship and for missions. Messages from players you muted and your own messages never make a sound. Choose OFF, Player Joined (ship default), Player Left, Menu Tab, Menu Subtab, Option Click, or one of five louder sounds: Menu Confirm, Menu Back, Action Wheel (mission default), Item Purchase and Confirmation Dialog. The mission setting also offers two sounds the game only has in missions: Reinforce Request (the sound of a dead player asking to be reinforced) and Countdown. Applying a sound in the menu plays it once so you can hear it.
- **Paste (Ctrl+V):** while you type in the chat, Ctrl+V adds the copied text after what you already typed, up to the chat's own length limit. Line breaks become spaces; emoji are left out.
- **Translation (highly experimental):** other players' messages translated for you (on by default), your own messages sent translated (untested, off by default), through Google Translate or your own service. See [Chat translation](#chat-translation-highly-experimental) below.
- The settings are in [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) (escape menu > MODS > Better Chat), grouped with a space between groups (Mod Options Menu 1.2 or newer). Without it, the defaults apply: the Player Joined sound on the ship and Action Wheel in missions, the game's chat size, paste, and inbound translation through Google into your Windows regional format's language.
- The settings' names follow the game's Text Language.

## Chat translation (highly experimental)

### Inbound Language: other players' messages

Each message from another player is translated, and the translation is added to your chat right below the original, under the same player's name, starting with the language it came from (for example `[EN] ...`). The original message always stays.

- **Only you see these translations.** They are added to your own chat on your own PC; the other players still see only the original message.
- **Pick the language:** **Automatic** (default) uses the language of your Windows regional format (Settings > Time & language > Language & region), which is often your own language even when Windows or the game is in English; **Game Language** uses the game's Text Language; or pick one of the game's languages. Messages already in that language are not translated. **OFF** turns inbound translation off.
- **Inbound Debug** (off by default) also translates your own messages, so you can try translation alone.
- Very short messages written only in Latin letters (fewer than 4 letters, like "gg", "o7" or "ez") are not translated: they would be mistaken for other languages.

### Outbound Language: your messages (untested)

Off by default. Pick a language and, when you press Enter in the chat, your message goes to the Translation Service first and the translation is sent in its place: **the squad sees only the translation**, under your name, about a second later (1-3 seconds with a custom service). If translation fails, takes too long, or your message is already in that language, your message is sent as you wrote it, so nothing is lost.

**Untested:** taking your message and sending the translation works when playing alone, but whether squadmates receive the translation has not been confirmed yet. Reports welcome in the [issues](https://github.com/Alomare/BetterChat/issues).

### Translation Service

- **Google Translate** (default): free, no account. Uses Google's keyless public addresses.
- **Custom:** your own AI translation service, with your own key: DeepSeek, Qwen (Alibaba Cloud), GLM (Zhipu), OpenAI or any other service with an OpenAI-compatible API, or a model running on your own PC through Ollama or LM Studio. Useful where Google is blocked (such as mainland China), or for better translations of slang. See [Setting up a custom service](#setting-up-a-custom-service).

### Setting up a custom service

1. **Get an API key** from the service you want (for example [DeepSeek](https://platform.deepseek.com), [Alibaba Cloud Model Studio](https://www.alibabacloud.com/product/modelstudio) for Qwen, [Zhipu BigModel](https://open.bigmodel.cn) for GLM, or [OpenAI](https://platform.openai.com)). Most charge per use and may need a small balance first; a chat message costs a tiny fraction of a cent. For a local model, install [Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai) and download a model instead: no key, nothing leaves your PC.
2. **In the game**, open escape menu > MODS > Better Chat, set **Translation Service** to **Custom** and apply. Better Chat writes the file `BetterChat_service.json` into `%LOCALAPPDATA%\CowboyBingus\Helldivers2` (next to the Logs folder, not inside it). Nothing is translated yet.
3. **Open that file** in Notepad (paste `%LOCALAPPDATA%\CowboyBingus\Helldivers2` into the Explorer address bar). Its `examples` section lists the address and a model for each service above. Copy your service's `base_url` and `model` into the fields at the top, and put your key between the quotes of `api_key`. For DeepSeek:
   ```json
   "base_url": "https://api.deepseek.com/v1",
   "api_key": "sk-your-key-here",
   "model": "deepseek-v4-flash",
   ```
   For Ollama: `"base_url": "http://localhost:11434/v1"`, `"api_key": ""` and the name of a model you downloaded (for example `"qwen3:8b"`). Save the file.
4. **Back in the game**, switch Translation Service to Google Translate, apply, then back to Custom and apply: Better Chat reads the file again. The log (`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BetterChat.log`) then says `Custom service ready: <address>, model <model>`, or `Custom service off:` with the reason (for example `model is empty`).
5. **Try it:** turn on Inbound Debug, set Inbound Language to another language and type a message in the chat. The translation appears under it after a second or two.

If nothing appears, look in the log for a line such as `Translation 1 (...) failed: done, curl exit 0, HTTP 401, ...`: 401 means the key is wrong, 402 or 429 usually means the account has no balance or hit its limit, 404 or 400 often means the model name is wrong (model names change: pick one from the service's model list).

**Optional settings in the file:**

- `prompt`: your own instructions to the model, replacing Better Chat's. It must contain `{language}`, which becomes the target language's name. Better Chat's own prompt asks the model to start its reply with the message's language code in brackets (`[de] ...`), which gives the `[DE]` label and lets a message already in your language be skipped; ask for the same in your own prompt.
- `glossary`: terms and how to write them, for example `{"Bile Titan": "Bile Titan", "o7": "o7"}` to keep them as they are. Up to 64 entries.
- **The game's official names are built in:** when translating into Simplified or Traditional Chinese, or from Chinese into English, Better Chat tells the model the official names of the game terms a message mentions (157 enemies, stratagems, weapons and objectives, taken from the game's own text). Your glossary takes precedence.

Only `http://` addresses on your own PC (localhost) are accepted besides `https://`, so a key can't be sent unencrypted over the internet.

### What is sent, and to whom

- **Google Translate:** while Inbound Language is not OFF, the text of each message from another player (and your own, with Inbound Debug) is sent to Google at `translate.googleapis.com`, together with the language to translate into. With Outbound Language on, the text of each message you send is sent too. No player names or game data are sent; like any web request, it comes from your internet connection, so Google sees your IP address.
- **Custom:** the same message texts, Better Chat's prompt (or yours), the matching glossary terms and your key are sent to the `base_url` you set, and nowhere else. What the service does with them is up to its own terms.
- **Nothing is sent while both Inbound Language and Outbound Language are OFF.** Messages and translations are not written to the mod's log, and neither is your key or the service file's location.
- Requests go through the `curl.exe` that ships with Windows, started in the background without a window. While a translation is on, curl is also started once per session with nothing to do (nothing is sent), so that a slow first start does not stutter the game when a message arrives.

### Why highly experimental

- Google's addresses are unofficial: Google can limit, change or close them at any time, as it did with the one earlier versions used. Translation then stops working (the chat itself is unaffected). A custom service doesn't depend on them.
- Each translation takes about half a second to a second and a half with Google, 1-3 seconds with a custom service.
- Machine translation of short, slangy chat can be wrong or odd.
- Outbound translation is untested with other players.
- It needs `curl.exe`, which Windows 10 (version 1803 and later) and Windows 11 include. It does not work on Linux or Steam Deck (Proton).
- It has been tested by a few players only.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Optional: [Mod Options Menu](https://www.nexusmods.com/helldivers2/mods/16625) for the settings.
3. Install the ZIP from [Releases](https://github.com/Alomare/BetterChat/releases) with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy. Keep Bingus Shared Loader last in the mod order, so it loads first.

The verdict is the first line of `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BetterChat_STATUS.log`.

## Technical Details

- **New messages.** The game keeps the chat's last 64 lines in a ring (first index, line count, then each line's sender, time and text). Every 200 ms the mod reads the ring's first index and count in one 8-byte read; when lines were added, it reads their senders and compares them with the local player's peer id. A new session or a cleared history only sets a new baseline. The game drops muted players' lines before they reach the ring.
- **The sounds.** Posted through the game's UI sound function. The first five sound ids are read from the game code that plays them: the HUD feed's player joined and left notices (with a ship and a mission variant), the menu tab bar's buttons, the standard menu button and an option row's arrow. The five louder sounds are given by the game's own id for them, which is a hash of the sound's name (the upper half of MurmurHash64A) and so stays the same across game updates; each exists in both of the game's UI sound banks, the ship's and the missions'. They were picked from a loudness survey of the game's UI sounds (`research/sound_survey.py`). Reinforce Request and Countdown are given the same way but exist only in the missions' bank, so only the mission setting offers them; Reinforce Request starts after a second of silence, as the game plays it. The game mode (ship or mission) picks which setting applies. The 2-second cooldown counts the frame time the game passes to the Lua update.
- **The size.** The chat widget is found inside the HUD and scaled with the game's own widget scale setter, relative to its own scale. It is checked every 30 frames, so a rebuilt HUD (after loading) gets the size again; a widget not laid out yet is left alone.
- **Paste.** On Ctrl+V (Windows' key state, with the game window in front) while the chat widget's text input is open (its open flag is read every 100 ms; the keys are read only while it is open, since Windows' key state call can take several milliseconds), the clipboard's Unicode text is cleaned (line breaks and tabs to one space, other control characters and characters outside the Basic Multilingual Plane left out), added to the field's current text, cut to the field's own character limit on character boundaries, and set through the game's text widget setter, the same call the game uses for Steam's text input.
- **Translation requests.** Windows' `curl.exe` runs with the constant command line `curl.exe -K -`: the request (address, options, the line and, for a custom service, the key, all quoted and escaped so a line can't add options) goes in through its standard input as a curl config, so neither the line nor an address is ever on a command line (the first start of a curl with an address on its command line took a few hundred milliseconds in the game). curl runs without a window and receives only its own pipe ends, and its reply is read from a pipe every frame, so the game only waits for curl to start (a few milliseconds). curl is also started once in advance, as soon as a translation is on, with an empty config: it exits at once and sends nothing. One request at a time (up to 8 lines wait, your outbound messages first), a server or network error is retried once, a request still running after 12 seconds (18 for a custom service) is ended.
- **Google.** Two keyless addresses, `translate_a/t?client=dict-chrome-ex` first and `translate_a/single?client=gtx` second, both with automatic source detection; when one answers HTTP 429 or 403, the other is used for the rest of the session and the line is sent again at once. The reply's detected language is compared with the target (Brazilian and European Portuguese count as one language; Simplified and Traditional Chinese don't).
- **Custom service.** A POST to `<base_url>/chat/completions` with the model, a system prompt naming the target language (plus the glossary and game terms the line mentions) and the line as the user message; no temperature or token limit, which some models reject. The reply's `[xx]` code plays the part of Google's detected language; reasoning blocks (`<think>`) and quotes are left out. The game terms are generated by `research/glossary.py` from the game's localized strings.
- **Inbound.** A translation is added through the game's own chat add-line, under the original sender, which only adds the line to the local chat; the added line is taken as the new baseline, so it makes no sound and is never translated again.
- **Outbound.** While the chat's text input is open and Outbound Language is on, the field's text and the Enter key are read every frame. On Enter, the text is taken and the field emptied through the game's text setter before the game's own chat update runs (the game then sends nothing and closes the input); the result is sent through the game's own chat send, the function the chat box calls, cut to the field's character limit. A translation the game refuses to send is sent again as written.
- **Finding the game's code.** Every global, native function and structure offset, and the first five sound ids, come from 18 code signatures generated in one block by `research/signatures.py` from a game.dll dump and checked to match exactly once. Each is tried at the known build's address first, else game.dll's executable sections are searched over a few frames; values are read from the matched instructions and repeated values must agree. Without the chat's code the mod turns off; without a sound's, the size's, paste's, the add-line's or the chat send's code, only that part does. The search engine (`tools/sigscan.lua` in the author's workspace) is shared with the author's other mods.
- **Texts.** `locales/en.lua` is the English source and `locales/<tag>.lua` the bundled translations, resolved by CowboyBingus' `src/bingus_text.lua` against the game's Text Language; the build places both ahead of the script.
- **Diagnostics.** An update of the mod that takes more than 4 ms is written to the log with the time of each part (at most 40 per session).
- **Memory access.** Reads go through `ReadProcessMemory` on the game's own process, which fails instead of crashing on a bad address. The mod never writes game memory itself; the game's own functions play the sound, set the size, set the pasted text, add the translations and send your translated messages.
- **Tests.** `tests/test_release.py` runs the built entry under LuaJIT against a game.dll dump (not included), with the chat ring, the HUD, the game's sound, scale, text, add-line and send functions, curl, both translation services, the clipboard and Mod Options Menu simulated.

How it works in the game's code: [RESEARCH.md](RESEARCH.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Credits

- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus, whose `bingus_text.lua` provides the translations.
- [spkel-max](https://github.com/spkel-max) proposed outbound translation, the OpenAI-compatible custom service and a built-in Chinese glossary in [pull request #2](https://github.com/Alomare/BetterChat/pull/2); V6 rebuilds those ideas.
- Game terms from the game's own localized text, read with [FileDiver](https://github.com/xypwn/filediver).
- Developed with Claude Opus 5.5 and the [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill).

## License

Copyright (C) 2026 Alomare. Licensed under the [GNU General Public License v3.0 or later](LICENSE): you're free to use, study, change and share this mod, and anything you distribute that includes or changes its code must use the same license and come with its source. `src/bingus_text.lua` is CowboyBingus's, under the Zero-Clause BSD license.
