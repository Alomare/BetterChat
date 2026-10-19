# Changelog

Releases are named "Better Chat V&lt;n&gt;" (tag `v<n>`). Each section is that release's notes.

## V6 (2026-10-19)

**Your settings start over:** the options were regrouped and most have new ids, so this version starts with its defaults (Sound Alert on, Player Joined on the ship, Action Wheel in missions, Inbound Language Automatic, Outbound Language OFF). Set them again in escape menu > MODS > Better Chat.

### Translation fixed (still highly experimental)

- **Fixed translations no longer appearing.** Google started refusing the free address Better Chat used, as "automated queries" (HTTP 429), for whole networks. Better Chat now asks a second free Google address first, and when one of them refuses, it switches to the other for the rest of the session and sends the same message again right away.
- **Inbound translation is now on by default** (Inbound Language: Automatic). Set Inbound Language to OFF and nothing is sent anywhere.

### New: Translation Service

- **Choose who translates:** Google Translate (default: free, no account) or **Custom**: your own AI translation service with your own API key. DeepSeek, Qwen (Alibaba Cloud), GLM (Zhipu), OpenAI and any other OpenAI-compatible service work, as do models running on your own PC through Ollama or LM Studio (no key needed). Useful where Google is blocked, such as mainland China, or for better translations of slang. Step-by-step setup in the README and on the Nexus page.
- **Set up in one file:** the first time you pick Custom, Better Chat writes `BetterChat_service.json` next to its Logs folder (`%LOCALAPPDATA%\CowboyBingus\Helldivers2`), with examples to copy for each service. Fill in the address, key and model, save, and apply Translation Service again. The key stays in that file: it is never written to the log, and it is sent only to the address you set.
- **Your own prompt and glossary (optional):** replace Better Chat's instructions to the model (they must contain `{language}`), and list terms with how you want them written.
- **The game's official names:** when translating into Simplified or Traditional Chinese, or from Chinese into English, the custom service is told the official names of the game terms a message mentions (157 enemies, stratagems, weapons and objectives, taken from the game's own text), so a Bile Titan becomes the name Chinese players see in their game, and back.
- A translation from the custom service takes about 1-3 seconds, depending on the service and model.

### New: Outbound Language (untested)

- **Send your messages translated.** Pick a language and, when you press Enter in the chat, your message goes to the Translation Service first and the translation is sent in its place: the squad sees only the translation, about a second later. If translation fails, takes too long, or your message is already in that language, it is sent as you wrote it. OFF by default.
- **Untested with other players:** the message is taken and sent as expected when playing alone, but whether squadmates receive the translation has not been confirmed yet. Please report how it goes.

### Settings reworked

- The settings are grouped, with a space between groups: Chat Size | Sound Alert, Sound Alert in Ship, Sound Alert in Mission | Translation Service, Inbound Language, Outbound Language | Inbound Debug. (The spaces need Mod Options Menu 1.2 or newer.)
- **Sound Alert** is a new on/off switch for the sounds; the two sound choices no longer have OFF. Sound Alert in Mission now starts at Action Wheel, which is easier to hear in combat.
- **Inbound Language** replaces Translate Chat and Translate To: OFF, Automatic (your Windows regional format's language), Game Language, or one of the game's languages.
- **Inbound Debug** replaces Translate My Messages: your own messages are translated too (only you see it), to try translation alone.
- Removed Sound Alert on My Messages.
- Translated every new setting and description into every game language.

### Thanks

- [spkel-max](https://github.com/spkel-max) proposed outbound translation, an OpenAI-compatible custom service and a built-in Chinese glossary in [pull request #2](https://github.com/Alomare/BetterChat/pull/2); this release rebuilds those ideas. Thank you!

## V5 (2026-10-10)

- Split New Message Sound into Sound Alert in Ship and Sound Alert in Mission. Sound Alert in Ship keeps your current choice; Sound Alert in Mission starts at Player Joined.
- Added two sounds to Sound Alert in Mission: Reinforce Request and Countdown.
- Added Sound Alert on My Messages, off by default: your own messages also play the sound, to try the sounds alone.
- Fixed a short freeze when a translation started, mostly on the first translated message.
- Fixed small stutters caused by the paste shortcut while playing.
- Translated the new settings into every game language.

## V4 (2026-10-06)

- Added five louder choices to New Message Sound: Menu Confirm, Menu Back, Action Wheel, Item Purchase and Confirmation Dialog.
- Removed the Paste (Ctrl+V) setting: paste is always on.
- Translated the new choices into every game language.

## V3 (2026-10-06)

- Added Paste (Ctrl+V), on by default: pastes the copied text into the chat while you type.
- Added Translate Chat (highly experimental), off by default: other players' messages are translated through Google Translate and the translation is added below the original. Only you see the translations.
- Added Translate To: Automatic (your Windows regional format's language), Game Language, or one of the game's languages.
- Added Translate My Messages, off by default: also translates your own messages, to try translation alone.
- Translated the new settings into every game language.

## V2 (2026-10-06)

- The chat is now checked for new messages every 200 milliseconds instead of every frame.
- Removed the space between the two options in Mod Options Menu.

## V1 (2026-10-06)

- First release: a sound when another player sends a chat message (at most once every 2 seconds), with six choices of the game's own sounds.
- Added a Chat Size setting, from 50 to 200%.
- Translated into every game language.
