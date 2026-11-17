# FB2AudioPrep visual and interaction design

## Product direction

A quiet, book-first interface: visually warm, restrained, typography-led, and never like a developer utility. Use ReadEra's low-friction library, Moon+ Reader's useful reading controls without its settings overload, and Kindle's calm reading surface. KOReader's power-user controls should remain optional and out of the primary path.

## Visual language

- Backgrounds: warm paper (#FAF8F3), dark charcoal (#1E2023), and sepia (#EFE5CF).
- Text: high-contrast charcoal/ivory, muted secondary labels, one restrained warm accent.
- Reading type: serif body text, sans-serif navigation and controls.
- Spacious layout, consistent 8dp rhythm, subtle dividers, rounded surfaces only for grouped controls.
- Avoid gradients, loud saturated colors, ornamental book-cover effects, unnecessary animations, and dense toolbars.
- Respect Android system font scaling, touch target sizing, contrast, and accessibility labels.

## Information architecture

### 1. Library (home)
- Header: app title and one compact search action.
- Main action: “Открыть книгу”.
- Continue reading card with cover/monogram, title, author (if known), progress and “Продолжить”.
- Library list/grid toggle, sort by last opened/title/author, filter by FB2/TXT.
- Empty state explains how to import a local FB2/TXT file. No account, cloud, or online catalog required.
- Recently opened books should be visually prominent; file-processing tools belong in a secondary “Подготовка текста” area.

### 2. Reader
- Full-screen reading area with generous margins and a readable serif face.
- Compact top bar: back, shortened book title, typography settings, overflow menu.
- Three themes: warm paper, dark, sepia.
- Typography settings: four useful sizes and three line spacings; persist per book.
- Bottom progress line and percent; persist scroll position and resume on reopen.
- Contents, in-book search, save/jump to bookmark from a small overflow menu.
- Do not show a permanent row of tiny controls over the text.
- Future audio player appears as a bottom mini-player only when playback is active; tapping expands the full player.

### 3. Audio player (both modes)
- Full player: large play/pause control, previous/next paragraph, seek/progress, playback speed, sleep timer, and current chapter.
- Mode switch: “Персонажи” / “Один голос”.
- Character mode: compact cast list with editable male/female voice assignments and fallback voice; do not overload the player with a full cast editor.
- Single voice: one voice selector and one preview action.
- Download/model status is a separate setup screen, not mixed into the reading controls.
- Clear states: model not installed, downloading, verifying, ready offline, insufficient storage, and failed download.
- Never imply audio playback works until the ONNX engine and audio service are integrated and tested.

### 4. Text preparation
- Keep accentuation and dialogue correction as a guided workflow: Import → Analyze → Review → Export.
- Put advanced controls behind “Дополнительно”.
- Show counts and confidence labels, but do not overwhelm the user with raw model diagnostics.
- User corrections must be easy to find and edit later.

## Interaction rules

- One primary action per screen.
- Use plain Russian labels; avoid technical terms such as ONNX, tokenizer, inference in user-facing UI.
- Destructive actions require confirmation.
- Preserve book progress, theme, font size, line spacing, bookmarks and character corrections locally.
- Offline-first: no login, no telemetry dependency, and no network requirement after the optional model pack is verified.
- Loading and errors must explain what the user can do next.

## Current implementation scope

The v4 patch upgrades the full-screen reader with warm/dark/sepia palettes, serif typography, adjustable font size and line spacing, contents, in-book search, bookmarks, and saved reading position. The library redesign and actual audio player remain subsequent implementation stages; playback controls must not be presented as functional until the engine is connected.
