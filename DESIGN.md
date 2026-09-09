---
name: ThetaRadar
description: A cool-gray fiduciary workbench that turns SEC filings into source-tagged investment theses, marketed as ThetaRadar with Financial Analyst as the product.
colors:
  cool-canvas: "#f5f6f7"
  paper: "#ffffff"
  paper-quiet: "#fafbfc"
  paper-sunken: "#f1f2f4"
  hairline: "#e6e7e9"
  hairline-strong: "#d8dade"
  input-stroke: "#c9ccd1"
  charcoal-ink: "#1d1f24"
  charcoal-deep: "#0e1013"
  charcoal-tint: "#eceef0"
  on-charcoal: "#ffffff"
  ink-muted: "#484c55"
  ink-faint: "#676b74"
  ok-text: "#137a4d"
  ok-bg: "#e7f4ed"
  ok-border: "#c3e0d0"
  danger-text: "#b23a2e"
  danger-bg: "#f9eae7"
  danger-border: "#eccbc4"
  warn-text: "#8a5f0a"
  warn-bg: "#f9f2e0"
  warn-border: "#e7d8ab"
  info-text: "#2b5f8f"
  info-bg: "#e9f0f6"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "clamp(2.3rem, 4vw, 3.2rem)"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "0.06em"
  data:
    fontFamily: "ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, Consolas, monospace"
    fontSize: "0.95rem"
    fontWeight: 650
    letterSpacing: "0.01em"
rounded:
  control: "9px"
  card: "14px"
  pill: "999px"
  small: "8px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.charcoal-ink}"
    textColor: "{colors.on-charcoal}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.charcoal-deep}"
  button-primary-disabled:
    backgroundColor: "{colors.charcoal-tint}"
    textColor: "{colors.ink-faint}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.charcoal-ink}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-secondary-hover:
    textColor: "{colors.charcoal-ink}"
  button-ghost:
    textColor: "{colors.ink-muted}"
  button-ghost-hover:
    backgroundColor: "{colors.charcoal-tint}"
    textColor: "{colors.charcoal-ink}"
  text-input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.charcoal-ink}"
    rounded: "{rounded.control}"
    padding: "9px 13px"
    height: "40px"
  status-chip-accepted:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok-text}"
    rounded: "{rounded.pill}"
    padding: "4px 11px"
  status-chip-rejected:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger-text}"
    rounded: "{rounded.pill}"
    padding: "4px 11px"
  status-chip-saved:
    backgroundColor: "{colors.charcoal-ink}"
    textColor: "{colors.on-charcoal}"
    rounded: "{rounded.pill}"
    padding: "4px 11px"
  source-tag:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.info-text}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.card}"
  nav-link:
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.small}"
    padding: "7px 12px"
---

# Design System: ThetaRadar

## Overview

**Creative North Star: "The Fiduciary Workbench"**

Financial Analyst is the desk of someone accountable for the numbers: clean paper, exact figures, and trust earned through visible process. Every dossier step, gate decision, source tag, and measured number is laid out on white sheets that sit on a cool-gray canvas (#f5f6f7), separated by 1px hairlines rather than promoted with loud color or heavy shadow. The one accent in the room is the charcoal ink itself — reserved for the actions you take and the workflow state those actions produce. Nothing in the product reads as a market terminal: color never says "up" or "down," only "accepted," "rejected," "pending," "done," or "locked." The browser is the workstation; a dossier reads like a file open on the desk, not a dashboard. Public surfaces brand as ThetaRadar (thetaradar.me) with Financial Analyst as the product descriptor; the logged-in workspace topbar carries the Financial Analyst wordmark.

The system is one Inter stack — a neutral, tight sans-serif set to tabular numerals wherever a figure can be compared — with a monospaced face held strictly for the things that must not be misread: tickers, source keys, code. Density is moderate and calm: compact micro-labels (uppercase, tracked out) introduce tables and panels, 0.9rem is the working size for most interactive text, and long-form analysis prose runs wide (up to ~72ch) with generous line height because it is evidence to be read, not UI copy to be skimmed. Spacing is achieved through a small set of recurring values (8/12/16/20/28px gaps and paddings) and through hairline rules, which do most of the separation work.

Elevation is flat with ambient lift. Panels are flat at rest — white or #fafbfc fills separated from the canvas and from each other by 1px borders; only panels that must float above a busy context take a soft ambient shadow, in two steps: card and pop. There are no hard offset shadows, and no "border under a wide soft shadow" ghost treatment. The public homepage extends the same world unmodified: the same topbar grammar, the same dossier sheet, the same chips and source tags, with marketing copy kept in the product's own voice ("Measured, not claimed").

**Key Characteristics:**
- Cool-gray canvas (#f5f6f7) with white "paper" panels and #fafbfc quiet wells, separated by 1px hairlines.
- Charcoal (#1d1f24) is the sole accent; it owns primary actions, active navigation, filled step orbs, and the "saved" state.
- Quiet, desaturated workflow colors (green / red / amber / blue families) mark process state only — never market sentiment.
- One Inter family plus a mono face reserved for tickers, source keys, and code; tabular numerals wherever figures align or compare.
- 1px hairlines as the primary separation device; two soft ambient shadows (card, pop) for the rare floating panel.
- Rounded form language: 14px cards, 9px controls, full-pill chips and orbs.
- The six-step dossier strip — with its orb/badge state grammar — is the signature component and appears at full fidelity on the homepage.

## Colors

The palette is a cool-gray light-fintech workstation: a charcoal ink acting as both text and action color, a family of neutral surfaces and hairlines, and a set of quiet, desaturated workflow colors that never push past their role.

### Primary

- **Charcoal Ink** (#1d1f24): The single accent. Primary text, primary buttons, active nav underline and text, filled step orbs, the "saved" badge, the brand mark, selection, and focus outlines. Also the ink for all headings and body copy.
- **Charcoal Deep** (#0e1013): Hover state of Charcoal Ink on filled surfaces (buttons, filled orbs).
- **Charcoal Tint** (#eceef0): The quiet charcoal — hover fills on ghost/secondary buttons and nav pills, empty-state glyphs, chat bubbles from the user, peer chips, the `xbrl_fact` source chip, and neutral badges.
- **On-Charcoal** (#ffffff): Text and icon glyphs placed on filled charcoal (buttons, active orbs, saved badges).

### Neutral

- **Cool Canvas** (#f5f6f7): App and page background; the "desk." Also the canvas the paper panels sit on.
- **Paper** (#ffffff): Panels — cards, the dossier document, the topbar, method list, homepage bands and footer.
- **Paper Quiet** (#fafbfc): Wells and alternate fills — raised row hover on tables, price/metric cards, done-mark tray, chat messages.
- **Paper Sunken** (#f1f2f4): Track fills — meters, progress bars, scroll tracks, disabled button fills.
- **Hairline** (#e6e7e9): 1px dividers, card borders, table rules.
- **Hairline Strong** (#d8dade): Stronger rules — secondary button borders, progress segment rests, input-hover neighbors.
- **Input Stroke** (#c9ccd1): Default text-input and ticker-input borders.
- **Ink Muted** (#484c55): Secondary text — gate copy, chat text, method notes, hover-forward on ghost text.
- **Ink Faint** (#676b74): Tertiary text and metadata — subtitles, scope lines, table headers, placeholder text, timestamps.

### Workflow state colors

Used only to mark the state of the user's process — never to grade the market.

- **Ok** (#137a4d text / #e7f4ed fill / #c3e0d0 border): Accepted, done, saved-complete, verified — the "green light" of the workflow.
- **Danger** (#b23a2e text / #f9eae7 fill / #eccbc4 border): Rejected, errors, destructive actions (Reject, Remove, Log out on hover).
- **Warn** (#8a5f0a text / #f9f2e0 fill / #e7d8ab border): Gate-pending, locked, quota-exhausted, tier-unverified.
- **Info** (#2b5f8f text / #e9f0f6 fill): The grounding blue — source tags (and info/loading banners) carry this family.

### Named Rules

**The Charcoal Owns Action Rule.** Charcoal Ink is the only color used for an action surface, an active state, or a workflow-complete fill. Primary buttons, active nav, filled orbs, the saved badge: all charcoal. If a control needs to say "act," it goes charcoal — never a hue.

**The State-Not-Sentiment Rule.** Color marks the workflow — accepted/rejected/pending/done/locked — never the market. Green is never "the stock went up"; it means "accepted / done." Red is never "sell"; it means "rejected / danger." If a figure needs emphasis it gets weight and tabular numerals, not a sentiment color.

**The Grounding Chips Carry the Only Hue Rule.** Source tags (and the info banner) are the one place a saturated family (the info blue) appears on its own. The only colored chips in a report are the ones that point back at the filings — evidence earns the color.

## Typography

**Display Font:** Inter (with -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial fallback) — the only proportional family.
**Label/Mono Font:** ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas — held for identifiers and data.

**Character:** A single tight, neutral sans stack carries the whole system, optically hinted with `font-feature-settings: "cv11", "ss01"` and set to tabular numerals wherever numbers compare. There is no display face and no second proportional family; hierarchy is made with weight (550–700), size steps, and negative letter-spacing, never with a font change. The base size is 15px with 1.55 line height, which reads as "document," not "app chrome."

### Hierarchy

- **Display** (650, `clamp(2.3rem, 4vw, 3.2rem)`, line-height 1.06, tracking -0.035em): The homepage hero line only ("A stock thesis that shows its work."), held to ~14ch.
- **Headline** (650, 1.6rem, line-height 1.25, tracking -0.025em): Page titles (Portfolio, Library) and the auth-card title (1.5rem); the homepage closes on a clamp(1.9–2.6rem) echo of it.
- **Title** (650, 1.02–1.28rem, tracking -0.015 to -0.02em): Card heads and section titles; step-panel titles run larger (1.28rem), section-head h2s on the homepage run to 1.9rem with tracking -0.03em.
- **Body** (400, 15px base / 0.9–0.95rem working, line-height 1.55–1.7): Copy, tables, chat, analysis. Long-form analysis prose is capped near 72ch (`max-width: 72ch`) and reads at 0.95rem with 1.7 line height; supporting copy caps around 46–60ch.
- **Label** (650–700, 0.72–0.8rem, uppercase, tracking 0.05–0.06em): The system's micro-voice — table headers, panel titles, quota labels, section kickers inside dossiers, metric labels. Labels are the only uppercased text and stay small.
- **Data** (650, mono, 0.82–0.95rem): Tickers in tables and workspace titles, source keys, ticker inputs, peer chips. Set with tabular numerals.

### Named Rules

**The Tabular Numbers Rule.** Any figure that can be compared or read as a column — prices, margins, ratios, step ordinals, progress counts, quota values — sets `font-variant-numeric: tabular-nums`. Numbers in this system never shift width, because a shifting digit reads as a changing fact.

**The Mono Means Identifier Rule.** The mono face is reserved for things that must not be misread or that identify a source: tickers, source keys (ITEM 1, FY2026, 10-K), ticker inputs, peer chips. Mono never types prose; prose never types tickers.

**The Inter-Only Rule.** One proportional family, one mono face, full stop. Headlines are not given a second face or a display serif — the "fiduciary" read comes from tight charcoal Inter and honest numerals.

## Layout

The system centers on a 1240px content column. The topbar and page container share the same max width; the homepage uses identical rails (its sections and bands are 1240px, band backgrounds bleeding edge-to-edge under the canvas). Horizontal page padding is 28px (20px under 1100px, 16px on the homepage under 760px); the topbar is 62px tall at rest and wraps under 760px.

Vertical rhythm is a short, repeated scale rather than a designed grid: component gaps of 8 / 10 / 12 / 14 / 16 / 20px, page stacks of 20px, section paddings of 72px on the homepage (56px under 1100px), and the close band breathing to 88–96px. Card interiors run 18–26px; the dossier document body is 26px top / 28px sides / 34px bottom (reduced to 20/18/26 under 760px). Separation between stacked blocks is done with 1px hairlines (section dividers, gate blocks, done trays) plus 20–30px breathing room, not extra shadow.

The primary interactive breakdown happens in the data tables: cells pad 14px 22px (18px under 760px), headers get 14px top / 22px sides / 10px bottom. Under 760px the Portfolio table re-cards each row: headers hide, each row becomes a white bordered card grid of `ticker / progress / status / chevron`, with uppercase field labels surfaced from `data-label`. The dossier step strip horizontally scrolls without a visible scrollbar at rest; under 760px a thin track and a right-edge fade are shown. Layout gaps are otherwise handled with flex and small `gap` values rather than margins.

## Elevation & Depth

Depth is conveyed almost entirely by surface tone and 1px hairlines on the cool-gray canvas. Panels are flat at rest: white cards and #fafbfc wells sit beside each other with hairline borders between them. Shadows are ambient and rare — they lift a floating panel off the desk, never outline it.

### Shadow Vocabulary

- **Card shadow** (`0 1px 2px rgba(23,25,31,0.04), 0 10px 30px -18px rgba(23,25,31,0.22)`): The default sheet shadow. Applied to every `.card` — portfolio/library tables, the dossier document, the method list, measure cards. A close, faint grounding shadow plus a wide, very soft falloff.
- **Pop shadow** (`0 2px 6px rgba(23,25,31,0.06), 0 18px 44px -20px rgba(23,25,31,0.32)`): The one-step-up layer for anything that must genuinely float above the page (menus, overlays). Defined and available; panels needing less lift stay at the card step.
- **Press shadow** (`0 1px 2px rgba(23,25,31,0.2)`): A close hair of shadow under charcoal-filled elements (primary buttons, saved badges) that gives a filled control a slight purchase on the sheet.
- **Focus ring** (`0 0 0 3px rgba(29,31,36,0.08)`): Inputs and ticker inputs shift to a charcoal border and pick up a 3px charcoal-at-8% ring on focus; generic keyboard focus draws a 2px charcoal outline with 2px offset.

### Named Rules

**The Ambient-Only Rule.** Shadows are soft, low-alpha, and diffuse (ambient), in exactly two steps — card and pop. There are no hard offset or hard-edged shadows anywhere, and no "1px border under a wide soft shadow" ghost pattern. When a surface must separate on the canvas, reach for a hairline first and a shadow only when it must float.

**The Flat-By-Default Rule.** Surfaces sit flat until they need to lift. A card at rest is tone + hairline; elevation is the exception a floating panel earns, never the resting state of every white rectangle.

## Shapes

The form language is a calm, rounded-but-not-soft system with three radius steps. Large document surfaces take the card radius of 14px (cards, the dossier document, SWOT cells, the method list). Controls and small containers take the control radius of 9px (buttons, inputs, banners, chat messages, price cards). Small pills in chrome take 8px (small buttons, nav pills, back links). Chips, badges, orbs, meters, and progress segments are full pills (999px); step orbs and verdict scores are circles. Radius never climbs past 14px, and nothing in the workstation is a hard 0px-corner square except the hairline rules themselves. The brand mark is a charcoal rounded square (8px) carrying a white check — a small statement of the "approval stamped in ink" idea that recurs in the orbs and saved badge.

## Components

### Buttons
- **Shape:** A quiet, restrained control — control radius (9px), sentence-case, no uppercase, no letter-spacing theatrics. Default padding 9px 16px at 0.9rem / 600. Sizes: `sm` 6px 12px at 0.84rem with an 8px radius; `lg` 11px 20px at 0.95rem. Active presses translate 1px down. Text stays left-aligned-in-flex with icons at an 8px gap.
- **Primary:** The one filled action. Charcoal Ink fill, white text, press shadow. Hover deepens to Charcoal Deep; disabled falls to a Charcoal Tint fill with Ink Faint text and no shadow — it visibly goes quiet rather than staying loud.
- **Secondary:** White paper fill, Charcoal Ink text, Hairline Strong border. Hover trades the border and text to Charcoal Ink — the action announces itself by going charcoal, not by filling. Disabled: Paper Sunken fill, Ink Faint text.
- **Ghost:** Transparent, Ink Muted text; hover gains a Charcoal Tint wash and charcoal text — a quiet button that wakes on the desk.
- **Danger:** The only hued button — Danger fill/text on a Danger border, darkening on hover. Reserved for Reject and other destructive or closing calls.

### Text Inputs
- **Style:** White paper fill, 1px Input Stroke border, control radius (9px), 40px min-height, 9px 13px padding. Inputs inherit the document voice (0.92rem) rather than imposing a control face.
- **Focus:** Border shifts to charcoal and a 3px charcoal-at-8% ring appears (outline removed). Hover (unfocused) warms the border one step past Hairline Strong.
- **Variants:** Placeholder text is Ink Faint at 85%; disabled drops to Paper Quiet with Ink Faint text. The ticker input is the one monospaced, semibold, 0.95rem input, for identifiers. Ingest and peer contexts get a leading icon inside the stroke (padding-left 40px).

### Cards / Containers
- **Corner Style:** Card radius (14px); small inline panels (price/metric cards, chat messages) use the 9px control radius instead.
- **Background:** Paper white for document surfaces and cards; Paper Quiet for compact wells (metric cards, price card, done-mark tray); Paper Sunken only as track/gutter fills, never as a content card.
- **Shadow Strategy:** Every card takes the card shadow by default (see Elevation); the portrait portfolio/library card at rest is the flagship use.
- **Border:** 1px Hairline on the canvas; none needed once a well sits on paper.
- **Internal Padding:** Headers 18px 22px; doc/analysis bodies 26px 28px 34px; compact wells 16–18px; the homepage proof card 24px 26px. Content inside a dossier step is padded to a 72ch measure.

### Chips
- **Status chips** — full pills, 4px 11px, 0.76rem / 650, tabular numerals, a 6px icon gap, 1px border in the same family. Variants: **Accepted/Ok** (Ok fill/text/border), **Rejected** (Danger triad), **Pending** (Warn triad), **Saved** (solid Charcoal Ink, white text — the only filled status chip), and **Muted** (Charcoal Tint with Ink Muted). These are the workflow-state vocabulary of the whole app and render identically on the homepage.
- **Badges** — the smaller, 3px 10px / 0.72rem pill for pass/fail/neutral call-outs inside tables and step strips.
- **Source tags (grounding chips)** — full pills, 2px 9px, 0.74rem / 600, tabular, sitting under analysis prose in a wrapping row behind a "Sources" micro-label. Base variant is the Info blue (Info fill/text) — the one place hue lives in a report. Filing-type variants restate the taxonomy quietly: filing → Warn family, XBRL-fact → Charcoal Tint with a stronger border.

### Dossier Step Strip (signature component)
- **Shape:** The six-step rail sits as a horizontal band across the top of the dossier document, split by 1px hairlines, each tab a flex column — a small orb over a step name and a sub-line. Each tab is ≥108px, padded 16px 14px 14px, and horizontally scrollable on narrow screens.
- **Step orb:** A 22px circle. At rest it is a numbered outline (1.5px Hairline Strong, Ink Faint). **Active** fills solid Charcoal Ink with white content; **done** becomes an Ok-tinted circle with an Ok check (stroke-width 3); a **rejected** step-1 orbs out in Danger text; **locked** turns the ring dashed on Paper Quiet with a lock glyph.
- **Step badge:** A tiny uppercase pill (0.62rem) at the tab's top-right, states mapping to workflow: Done/Ok, Rejected/Danger, Gate/Warn, Open/Charcoal Tint.
- **State language:** Active tab name is charcoal; locked steps mute the name to Ink Faint at 550 and never hide — a locked step stays visible with its reason in the sub-line ("mark Steps 2-4 done"). Tabs hover to Paper Quiet unless locked.

### Tables
- **Data table:** 1px hairline rules, no vertical strokes. Header micro-labels (0.72rem / 650 / uppercase / tracked) over a hairline; cells at 0.9rem with 14px 22px padding and 1px row rules (last row bare). Rows are keyboard-operable buttons; hover raises the whole row to Paper Quiet and slides a charcoal chevron into the right cell. Tickers render in mono, bold, 0.95rem.
- **Matrix (numbers tables):** Right-aligned, tabular-nums throughout; the row label sticks left with `position: sticky` as you scroll, and rows raise to Paper Quiet on hover. Below 760px the Portfolio table re-cards rows into stacked white cards (see Layout).
- **Progress segments:** A six-dot, 18px-wide bar (`pdot`), Hairline Strong rests filling charcoal one by one, beside a `3/6` tabular count.

### Auth Card
- **Style:** A single 440px-max white card centered on the cool canvas, the paper stage for the whole act of signing in. Interior padding 40px 42px (32px 26px under 760px) around a brand row, a 1.5rem title, an Ink Faint subtitle, and a stacked 12px-gap form. The primary submit button goes full-width with a 44px min-height; a Charcoal Tint note well sits beneath for tier/verification context.

### Navigation
- **Topbar:** A sticky white bar at 92% opacity with a `saturate(1.4) blur(10px)` frost and a hairline bottom edge; 62px tall, 28px side padding. Brand: a charcoal rounded-square mark (with the white check) beside the wordmark. Public surfaces stack a ThetaRadar wordmark (650, 0.98rem, tight) over a small tracked uppercase Financial Analyst descriptor; the logged-in workspace topbar uses the single "Financial Analyst" wordmark. Section tabs (navtab) are quiet pills — Ink Muted at 550 that wash Charcoal Tint on hover; the active tab carries charcoal text plus a 2px charcoal underline near the bar's bottom edge. Under 760px the nav drops to its own hairline-topped row.
- **Homepage nav:** The same header grammar (frost, hairline, 62px) with plain text links — 0.9rem / 550 — that pill on hover; no active underline is needed on a one-page surface. The right cluster pairs a Ghost **Log in** with a Primary **Get started**.
- **Homepage hero + bands:** A two-column 5fr/6fr hero (copy beside a live sample dossier) that collapses to one column under 1100px; full-bleed white bands with hairline top/bottom borders alternate with canvas sections; a centered close band and a hairline-topped footer close the page.

## Do's and Don'ts

### Do:
- **Do** lead with the workflow state colors for process, and reserve charcoal for the single action or active thing on screen.
- **Do** set tabular numerals on every number that can be compared or read in a column — prices, ratios, progress, step ordinals.
- **Do** separate stacked blocks with 1px hairlines and 20–30px of breathing room before reaching for a shadow.
- **Do** keep the dossier step strip's lock language visible — a locked step stays on the rail, muted, with its reason readable in the sub-line.
- **Do** set long-form analysis prose in the body measure (~72ch) at readable size, and keep supporting copy under ~60ch.
- **Do** put tickers, source keys, and code in the mono face, never prose.

### Don't:
- **Don't** use green/red as market-up/market-down sentiment; those families mean accepted/done and rejected/danger only.
- **Don't** add a second proportional typeface, an uppercase headline, or letter-spaced body text — hierarchy is weight and tracking on Inter alone.
- **Don't** introduce hard offset shadows, colored drop shadows, or a "border under wide soft shadow" card treatment.
- **Don't** give a chip or status any hue other than the workflow families (Ok/Danger/Warn) or the Info grounding blue.
- **Don't** radius a document surface past 14px or a control past 9px; chips and orbs are the only full pills besides progress meters.
- **Don't** add a border to an element sitting on paper — hairlines separate paper from canvas, not paper from paper.
