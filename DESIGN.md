---
name: NotForgotten
description: A terminal sign system for spaced-repetition study; the exam is the departure.
colors:
  signal-yellow: "#ffcc00"
  signal-yellow-deep: "#f2b900"
  sign-black: "#0b0b0b"
  ink-2: "#3a3a36"
  ink-3: "#5d5c55"
  ground: "#e6e6e6"
  panel: "#ffffff"
  panel-2: "#f4f4f2"
  board-row: "#151515"
  board-text: "#f3f3f0"
  board-dim: "#8d8d86"
  status-final: "#ff8a1f"
  status-rebook: "#ff5a4a"
  status-checkin: "#8fb7ff"
  ok: "#138a3b"
  bad: "#c62a1c"
  heat-0: "#ececea"
  heat-1: "#f6dc7a"
  heat-2: "#e6b300"
  heat-3: "#a87e00"
  heat-4: "#5e4600"
  night-ink: "#f3f3f0"
  night-ink-2: "#c9c9c2"
  night-ink-3: "#9a9a92"
  night-ground: "#101010"
  night-panel: "#1a1a1a"
  night-panel-2: "#222221"
  night-rule: "#3c3c38"
  night-board: "#050505"
  night-ok: "#4ad07a"
  night-bad: "#ff6b5c"
typography:
  display:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(3.2rem, 8.4vw, 6rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(2rem, 4.2vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 700
    lineHeight: 1.5
  board:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, SF Mono, monospace"
    fontSize: "0.98rem"
    fontWeight: 400
    lineHeight: 1.5
  status:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, SF Mono, monospace"
    fontSize: "0.86rem"
    fontWeight: 700
    letterSpacing: "0.08em"
  board-columns:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, SF Mono, monospace"
    fontSize: "0.72rem"
    fontWeight: 400
    letterSpacing: "0.12em"
rounded:
  flap: "2px"
  r: "4px"
  r-lg: "8px"
spacing:
  band-pad: "clamp(20px, 3vw, 40px)"
  panel: "20px"
  grid-gap: "20px"
  page-gap: "28px"
  rail: "272px"
components:
  button-primary:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.panel}"
    typography: "{typography.label}"
    rounded: "{rounded.r}"
    padding: "0 18px 0 0"
    height: "46px"
  button-primary-night:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r}"
    height: "46px"
  button-yellow:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r}"
    height: "46px"
  button-secondary:
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r}"
    height: "46px"
  button-big:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.panel}"
    rounded: "{rounded.r}"
    padding: "0 26px 0 0"
    height: "64px"
  button-sm:
    rounded: "{rounded.r}"
    height: "36px"
  pictogram:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.panel}"
    rounded: "{rounded.r}"
    size: "46px"
  pictogram-lg:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.panel}"
    rounded: "{rounded.r-lg}"
    size: "clamp(64px, 7vw, 96px)"
  sign-band:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.sign-black}"
    typography: "{typography.headline}"
    padding: "{spacing.band-pad}"
  rail-link-active:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.signal-yellow}"
    padding: "12px 8px"
  departure-board:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.board-text}"
    typography: "{typography.board}"
    rounded: "{rounded.r-lg}"
  board-row:
    textColor: "{colors.board-text}"
    typography: "{typography.board}"
    padding: "0 20px"
    height: "46px"
  status-chip:
    backgroundColor: "{colors.sign-black}"
    typography: "{typography.status}"
    rounded: "{rounded.r}"
    padding: "3px 8px"
  information-board:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r-lg}"
    padding: "{spacing.panel}"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r}"
    padding: "11px 14px"
  boarding-pass:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.r-lg}"
    padding: "22px 24px"
  boarding-pass-stub:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.board-text}"
    width: "240px"
    padding: "22px 20px"
  wayfinding-tile:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.sign-black}"
    padding: "22px {spacing.band-pad}"
  tabbar-mobile:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.board-text}"
    rounded: "{rounded.r-lg}"
    padding: "6px"
---

# Design System: NotForgotten

## Overview

**Creative North Star: "The Departures Hall"**

Every screen is an airport sign system. Signal yellow carries wayfinding: the left rail, the page sign bands, the wayfinding tiles and the next action. Sign black carries type, pictogram insets and the live departure boards, where concept recall is printed in yellow-and-white split-flap mono. White information boards on a gray ground hold the reading and the charts. The exam is the departure; memory state is a flight status word printed beside its number.

The world is read at a glance from across a hall: heavy humanist type at sign scale, square-ish 4px corners, 1px black rules between sign panels, arrows locked to the edge they point past. Density is high on boards (46px rows) and calm on reading surfaces. The night theme is a night terminal: ground goes near-black, primary actions and off-band pictograms light up yellow, the boards stay black.

The build refuses the sidebar-plus-stat-card SaaS dashboard: there are no tinted metric cards, no gradients, no decorative illustration. Depth is the sign stack itself (yellow over black over white), not floating shadow.

**Key Characteristics:**
- Signal yellow sign bands with black type; one band per page states the place and its decision.
- Black departure boards with split-flap mono cells and flight-status words.
- Memory status is a word plus a number, never colour alone.
- Atkinson Hyperlegible Next for everything humans read; Atkinson Hyperlegible Mono for everything a board prints.
- Square-ish corners (4px controls, 8px panels), 1px rules, 2px control borders.
- Black arrow insets on buttons, locked to the leading edge.

## Colors

Two sign colours and a gray hall: yellow says where to go, black says what is true, white and gray hold the reading.

### Primary
- **Signal Yellow** (signal-yellow): the sign plane. Left rail, page sign bands, Today's next-up band and wayfinding tiles, the boarding pass, selection highlight, focus halo, board headings and flap digits on black, and the primary button in the night theme.
- **Sign Yellow Pressed** (signal-yellow-deep): hover state for anything sitting on yellow (rail links, linked tiles). Never a standalone fill.

### Secondary
- **Sign Black** (sign-black): type on every sign, pictogram tiles, the active rail link, the primary button in the light theme, departure boards, toasts, tooltips, code blocks and the boarding-pass stub. Also the 1px rule colour on light surfaces.

### Tertiary (status lamps, on black only)
- **Status White** (board-text): ON TIME, recall 90% or higher.
- **Signal Yellow** (signal-yellow): BOARDING, recall 80 to 90%, review soon.
- **Final Call Amber** (status-final): FINAL CALL, recall 65 to 80%, review now. The word blinks three times on arrival, then holds.
- **Rebook Red** (status-rebook): REBOOK, recall under 65%, relearn it.
- **Check-in Blue** (status-checkin): CHECK IN, not learned yet.

Thresholds classify the rounded value the board prints (two decimals), so the word and the printed percentage never disagree. These lamps are only legible on black; on light surfaces a status word sits in a sign-black chip.

### Neutral
- **Hall Gray** (ground): the page ground behind information boards.
- **Board White** (panel) and **Board White Recessed** (panel-2): information boards, inputs, inline code, skeletons.
- **Secondary Ink** (ink-2) and **Tertiary Ink** (ink-3): labels, legends, muted copy, axis text.
- **Board Row** (board-row), **Board Text** (board-text), **Board Dim** (board-dim): departure-board hover row, row text, column headers and sublines.
- **Soft Rule** (rgba(11, 11, 11, 0.16); night rgba(255, 255, 255, 0.12)): dividers inside a board or panel. Panel outer edges use full-strength rules.
- **Correct / Wrong** (ok, bad): grading verdicts, error boxes and the danger button only.
- **Night terminal** (night-ink, night-ink-2, night-ink-3, night-ground, night-panel, night-panel-2, night-rule, night-board, night-ok, night-bad): replace their light counterparts under `prefers-color-scheme: dark` or `data-theme="dark"`. Signal yellow, sign black and the status lamps do not change.

### Heat ramp
- **Heat 0 to 4** (heat-0 through heat-4): the review-activity calendar, gray to ochre in light; the night ramp runs dark ochre to bright yellow (#262624, #4a3d0c, #7d6300, #c49a00, #ffd24a). Heat steps rise in lightness contrast as well as hue, and the exact count and minutes appear in the hover tooltip.

### Named Rules
**The Word-Plus-Number Rule.** Memory state is always printed as a status word and the recall number. Colour reinforces; it never carries the meaning alone. Recall bars are ten ink ticks, also paired with the number.

**The Lamps-On-Black Rule.** Status colours only render on a black ground (board, chip, stub). On yellow, white or gray, put the word in a sign-black chip.

**The Yellow Is Wayfinding Rule.** Yellow fills mark place and next action (rail, bands, tiles, pass, primary action at night). Information boards stay white or black; yellow never becomes a tinted card background.

## Typography

**Display Font:** Atkinson Hyperlegible Next (with Segoe UI, system-ui), self-hosted at 400, 500, 700, 800
**Body Font:** Atkinson Hyperlegible Next
**Label/Mono Font:** Atkinson Hyperlegible Mono (with ui-monospace, SF Mono), self-hosted at 400, 700

**Character:** A signage-legible humanist sans set heavy and tight for signs, plain for reading; its mono sibling is the voice of the boards, the flaps and the status words. Body numerals are tabular everywhere.

### Hierarchy
- **Display** (800, clamp(3.2rem, 8.4vw, 6rem), 0.95, -0.04em): landing hero title only. Today's next-up line uses the same weight at clamp(3rem, 5vw, 5.6rem), single line.
- **Headline** (800, clamp(2rem, 4.2vw, 3.6rem), 0.98, -0.035em): the sign band title on every page. Band subline is 500 weight at clamp(1rem, 1.4vw, 1.25rem), max 60ch.
- **Title** (800, 1.3rem, 1.08): panel heads; board heads are 1.5rem in signal yellow. Tile values are 800 at clamp(1.6rem, 2.4vw, 2.2rem).
- **Body** (400, 16px, 1.5): running text; prose blocks at 1.65 line-height, max 72ch.
- **Label** (700, 0.85rem): field and fact labels in ink-2, sentence case.
- **Board** (Mono 400, 0.98rem): board row data; row names switch back to the sans at 700.
- **Status** (Mono 700, 0.86rem, 0.08em, uppercase words by content): status words.
- **Board columns** (Mono 400, 0.72rem, 0.12em, uppercase): column headers on departure boards and boarding-pass field labels (sans 700, 0.75rem, 0.08em). These are the printed furniture of boards and passes, not section headings.

### Named Rules
**The Two Voices Rule.** The sans is for what people read; the mono is for what a board prints (data, flaps, status, column heads). Never set prose in mono or board data in the sans.

**The Sign Scale Rule.** Headings are 800 with negative tracking (-0.02em to -0.04em) and balanced wrapping; emphasis inside running text is 700 or 800, never colour.

## Layout

Desktop is a two-column shell: a sticky 272px yellow rail on the left and the main column on the right. Each page opens with a full-width sign band, then a page body with padding of clamp(20px, 3vw, 40px), a 28px vertical gap between sections, and a 1440px max width (960px for narrow pages). Grids use a 20px gap; panels pad 20px with 18px by 20px heads.

Today breaks the pattern deliberately: its top is an all-yellow sign split 0.95fr / 1.15fr between the next-up band and a black departure board, with three wayfinding tiles beneath, all separated by 1px black rules rather than gaps.

Responsive behaviour, from the build:
- **1100px:** multi-column page grids (Today split, Exams, Map, Insights, Library) collapse to one column; three-up grids become two; tiles stack with bottom rules.
- **900px:** the rail disappears and a fixed black tab bar (five tabs, 8px corners, 10px inset from the edges and safe area) takes over; the active tab is a yellow cell. Toasts and the tutor composer lift above it.
- **720px to 700px:** the boarding pass stacks its stub below with a dashed yellow top edge; two-up grids go single.
- **560px:** departure boards drop to three columns (56px, 1fr, 96px) and hide secondary columns.
- **600px:** review progress ticks hide; the landing nav button drops its arrow inset.

### Named Rules
**The Rules-Not-Gaps Rule.** Adjacent sign panels (rail links, tiles, Today's split, the time machine strip) are separated by 1px sign-black rules, not whitespace or shadows.

## Elevation & Depth

Flat by default. Depth comes from the sign stack: black boards and pictograms set into yellow, white boards set onto gray, each edged with a 1px rule. One soft shadow exists for things that genuinely float above the page, and buttons lift a pixel on hover.

### Shadow Vocabulary
- **Float** (`box-shadow: 0 1px 0 rgba(0, 0, 0, 0.08), 0 8px 24px -12px rgba(0, 0, 0, 0.35)`): the review card, toasts and chart tooltips.
- **Button lift** (`box-shadow: 0 6px 16px -8px rgba(0, 0, 0, 0.6)` with `translateY(-1px)`): button hover only.
- **Tab bar** (`box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6)`): the fixed mobile tab bar.
- **Focus halo** (`outline: 3px solid ink; outline-offset: 2px; box-shadow: 0 0 0 6px signal-yellow`): every focus-visible element; on yellow the halo flips to white with a black outline. Inputs take a 4px yellow ring on focus (black ring on yellow).

### Named Rules
**The Flat Sign Rule.** Panels, boards, tiles and bands carry no shadow at rest. A shadow means the element floats over the page (card in session, toast, tooltip, mobile nav).

## Shapes

Square-ish and engineered. Controls, chips, pictograms and inputs use 4px corners; panels, boards, the boarding pass, large pictograms and the tab bar use 8px; split-flap cells use 2px. Rail links and sign bands are square. Borders are 1px for panel edges and rules, 2px for interactive controls (buttons, inputs, segmented controls, stops). The only rounded-off forms are status dots and the tutor's chat bubble (12px with a 2px tail corner).

**The Locked Arrow Rule.** Arrows sit in a fixed square inset on the leading edge of a button, divided by a 2px rule, or at the trailing edge of a wayfinding tile; they never float free in a sentence.

## Components

### Buttons
Heavy, sign-like, with the arrow inset as a pictogram cell.
- **Shape:** 4px corners, 2px border in the fill colour, min-height 46px (36px small, 64px big).
- **Primary:** sign black with white 700 text in light; lit signal yellow with black text in the night theme, except on a sign band where it stays black. The leading arrow inset is 42px wide (34px small, 62px big), full height, separated by a 2px current-colour rule; the label padding is 18px on the trailing side only (26px big).
- **Yellow:** signal yellow fill, black text and border; used on black surfaces.
- **Secondary:** transparent with black border and text; on information boards the border follows ink.
- **Danger:** transparent with the bad colour as border and text.
- **Plain:** no arrow inset, 18px padding both sides.
- **Hover / Focus:** lift 1px with the button-lift shadow over 0.15s on the house ease; press returns to 0; disabled is 45% opacity with no lift.

### Chips
- **Status chip:** a sign-black capsule (4px corners, 3px by 8px) holding a status word in its lamp colour. Used wherever a status appears off a board.
- **Rail count:** mono 700 0.85rem, black on yellow, inverting on the active link.

### Cards / Containers
- **Information board:** white (night: #1a1a1a), 1px full-strength rule, 8px corners, no shadow; head 18px by 20px with a soft-rule divider, body 20px.
- **Wayfinding tile:** yellow sign cell, pictogram, key (700, 1rem), value at tile scale, small subline and a trailing arrow; deepens on hover.
- **Warn band:** a black band with an amber icon and yellow links, 8px corners.

### Inputs / Fields
- **Style:** 2px ink border, 4px corners, white fill, 11px by 14px padding, 1rem text; textareas min 120px. On yellow, inputs use a warm white (#fffdf2) with sign-black borders.
- **Focus:** a 4px signal-yellow ring (sign-black ring on yellow), no outline change.
- **Segmented control:** 2px bordered strip with 2px dividers; the pressed segment fills ink with ground-coloured text.
- **Error:** 2px bad-colour border box with 700 text.

### Navigation
- **Rail:** sticky yellow column, brand at top, links as rule-separated rows: 46px pictogram, label (700, 1.02rem) with a hint line (0.8rem), optional count. Hover deepens yellow; the active link inverts to black with a yellow pictogram and yellow text.
- **Mobile:** fixed black tab bar with five tabs, 0.72rem 700 labels under icons; active tab is a yellow 4px cell.

### Pictogram Tiles
Black squares with white line icons: 46px at 4px corners in the rail and lists, 34px small, clamp(64px, 7vw, 96px) at 8px corners in sign bands. An inverted yellow variant sits on black. In the night theme, pictograms on the page body (off the bands) become lit yellow tiles with black icons.

### Sign Band
The page header: full-width yellow plane with a 1px black bottom rule, padded by the band spacing; a large pictogram, the headline title, a subline, and right-aligned actions that wrap. Exactly one per page. The review session uses a sticky compact version with progress ticks (8px black bars, the current tick ringed yellow then black).

### Departure Board
The signature component. Black board, 8px corners, overflow clipped. Head: yellow 1.5rem title with a dim mono note on the right. Columns default to 64px / 1fr / 120px / 116px with 14px gaps and 20px side padding; column headers in board-columns mono, uppercase, dim. Rows are at least 46px, separated by #222 1px lines, mono data with the concept name in the sans at 700 and a dim sans subline; linked rows lift to the board-row tone on hover. Recall is a split-flap number, then the status word, then a ten-tick recall bar in the status colour.

### Split-Flap Cells
Mono 700 characters each set in a #1d1d1b cell with a 1px black hinge line across the middle, 2px corners, 1px apart. When the value changes, each character cycles through A to Z, 0 to 9, % and · at 55ms ticks and settles left to right with small random lag; the turning cell squashes vertically on a 90ms stepped animation. Under reduced motion the value swaps instantly. Flaps appear on boards, the boarding pass, the concept gate and the time-machine readout.

### Boarding Pass
The exam card. A yellow pass with a 1px black edge and 8px corners, main area padded 22px by 24px: field labels (0.75rem 700, 0.08em, uppercase), exam name at clamp(1.6rem, 2.6vw, 2.4rem), a "Departs in" countdown as large black-and-yellow flaps, a rule-topped field grid (auto-fit 112px minimum), then actions. A 240px black stub on the right, separated by a 2px dashed yellow tear line, forecasts recall on exam day in flaps with an on-track status. Below 720px the stub stacks under the pass with the tear line on top.

### Charts
Hand-built SVG on white information boards: one y-axis per chart, recessive soft-rule gridlines, mono 11px axis text in ink-3, 2px round-capped lines, 10% area fill at most, 5px hover dots with a 2px panel-coloured ring, a vertical ink-3 crosshair, and a black tooltip with the float shadow. The primary series is chart-1 (ink in light, signal yellow at night); the comparison series is chart-2 (ink-3 gray) and is always dashed, so series differ by stroke as well as colour. Thresholds are 1px dashed ink lines with an inline mono label. Legends use 16px by 3px swatches (dashed for dashed series).

### Motion
One ease for everything: `cubic-bezier(0.16, 1, 0.3, 1)`. Hover background changes 0.2s, button lift 0.15s, input focus ring 0.15s. Expressive motion is reserved for the board: split-flap settling and a three-blink FINAL CALL. All animation and transition collapses under `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** print every memory state as a status word plus its recall number, with thresholds 90 / 80 / 65% (ON TIME, BOARDING, FINAL CALL, REBOOK) and CHECK IN for unlearned.
- **Do** open every page with one yellow sign band carrying a large black pictogram, the place name and its next decision.
- **Do** put live, ranked or time-based data on a black departure board in Atkinson Hyperlegible Mono with split-flap numbers.
- **Do** lead buttons with the locked black arrow inset (42px, 2px divider) and keep primary buttons black in light and yellow in the night theme.
- **Do** separate adjacent sign panels with 1px sign-black rules and keep corners at 4px for controls and 8px for panels.
- **Do** dash the comparison series in every chart and keep one y-axis per chart.

### Don't:
- **Don't** use status colours on yellow, white or gray grounds; wrap the word in a black chip.
- **Don't** convey memory state or chart series by colour alone.
- **Don't** build sidebar-plus-stat-card dashboards, tinted metric cards or gradient fills; yellow is wayfinding, not decoration.
- **Don't** add resting shadows to panels, boards, tiles or bands; shadows are for floating elements only.
- **Don't** set prose or headings in the mono, or board data in the sans.
- **Don't** add decorative motion; motion is state feedback (0.15 to 0.2s transitions, loading shimmer, the tutor's typing and caret) or board vocabulary (flaps, FINAL CALL blink), and it always honours reduced motion.
