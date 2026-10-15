# Changelog

Releases are named "Better Chat V&lt;n&gt;" (tag `v<n>`). Each section is that release's notes.

## V7 (unreleased)

- Added bidirectional translation: **Outbound Translation** (off by default) and **Outbound Language** (default English). When on, a message you send is read from the chat's text field as you press Enter and the field is cleared before the game sends it; the translation is then sent to the whole squad through the game's own chat send, so only the translated text goes out. If the translation fails, your original is sent instead, so no message is lost.
- The game's chat send is read from the `chat_send` signature (the call it already matched), so no new code signature is needed.
- English source and Simplified/Traditional Chinese texts added; the other languages fall back to English until their translations are written.
- The Enter-frame ordering (the intercept clearing the field before the game sends it) has not been live-verified yet.

## V6

- Added Translation Service: Google Translate (default) or a custom OpenAI-compatible service. The custom service reads its address, API key, model and an optional system prompt from `BetterChat.custom.json` in the log directory (`{language}` becomes the target language's name).
- Custom-service requests go through the same hidden `curl.exe` as Google's: a POST to `base_url/chat/completions` with the line in a JSON body and the key in the `Authorization` header, all off curl's command line.
- `BetterChat.custom.json` is now created automatically (a template with the right shape) the first time the custom service is used, instead of only being described in the README.
- Translated the new settings into every game language (English source; Simplified and Traditional Chinese bundled).

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
