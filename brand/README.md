# Kantorei — Corporate Design

Eigenständiges Marken- und UI-Paket für das Notenarchiv. Stilrichtung **modern-reduziert**
(viel Weißraum, ruhiges Blau `#2E6EB5`, Schrift *Inter*). Ein System, drei Lichtwelten:
**Hell** (Verwaltung) · **Empore-Dunkel** (Spielmodus) · **Rotlicht** (Nacht-Empore).

## Inhalt

| Datei | Zweck |
|---|---|
| `styleguide.html` | **Lebender Style-Guide** — Logo, Farben, Typo, Komponenten, Interaktion, Muster-Screens. Im Browser öffnen, oben Theme umschalten. |
| `tokens.css` | **Single Source of Truth** — alle Farben/Typo/Abstände/Motion als CSS-Variablen (inkl. Dark-/Rotlicht-Theme). |
| `logo.svg` / `logo-inverse.svg` | Wortmarke (hell / für dunklen Grund). |
| `mark.svg` | Nur Bildmarke (Achtelnote), `currentColor`-fähig. |
| `icon.svg` | App-Icon, vollflächig (maskable-tauglich). |
| `favicon.svg` | Favicon (gerundete Kachel). |
| `icon-192.png` `icon-512.png` `icon-maskable-512.png` `apple-touch-icon.png` | Gerasterte PWA-/iOS-Icons. |
| `manifest.webmanifest` | PWA-Manifest, verweist auf die Icons. |

## Verwendung in der App

```html
<link rel="stylesheet" href="/brand/tokens.css">
<link rel="icon" href="/brand/favicon.svg">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon.png">
<link rel="manifest" href="/brand/manifest.webmanifest">
<meta name="theme-color" content="#2E6EB5">
```

Komponenten stets über die Tokens gestalten, nie Hex-Werte hart kodieren:

```css
.btn-primary{ background:var(--accent); color:var(--accent-ink); border-radius:var(--radius-sm); }
```

Theme setzen: `document.documentElement.dataset.theme = 'dark'` (bzw. `'rot'`, Standard = hell).

## Grundsätze

- **Blau = interaktiv.** Der Akzent markiert ausschließlich Bedienbares.
- **Tiefe durch Linie & Fläche**, kaum Schatten.
- **Trefferflächen ≥ 44 px**, Fokus sichtbar, alles per Tastatur bedienbar.
- **Motion kurz & funktional**, respektiert `prefers-reduced-motion`.
- Der **Name „Kantorei" ist austauschbar** — er lebt nur in den SVGs (`<text>…Kantorei…`) und im
  `manifest.webmanifest`. Umbenennen = dort ersetzen.

## Icons neu rendern

Die PNGs werden aus `icon.svg` / `favicon.svg` erzeugt (macOS QuickLook):

```bash
qlmanage -t -s 512 -o . icon.svg && mv icon.svg.png icon-512.png
qlmanage -t -s 512 -o . icon.svg && mv icon.svg.png icon-maskable-512.png
qlmanage -t -s 192 -o . icon.svg && mv icon.svg.png icon-192.png
qlmanage -t -s 180 -o . icon.svg && mv icon.svg.png apple-touch-icon.png
```
