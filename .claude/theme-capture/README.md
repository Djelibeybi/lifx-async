# LIFX app theme capture

Every theme palette in the LIFX mobile app, captured from hardware on
2026-08-14. This is the raw material for refreshing `src/lifx/theme/library.py`,
which has drifted badly from the app.

## Why this exists

The library's themes were transcribed from photons years ago and never
resynced. The app now ships 179 themes; the library carries 57, and most of the
ones it shares with the app no longer match.

Themes cannot be read out of the app bundle. They are server-driven —
`com.lifx.shared.data.cloud.themes.ThemeDTO`, cached in a local SQLite table —
so no theme name appears anywhere in the APK. The internal endpoints
(`api.lifx.com/themes/v2`, 401; `themes/v1/palette`, 405 POST-only) are
undocumented and were deliberately not called. That leaves the device itself as
the only accessible source of truth.

## How it was captured

Applying a theme as MORPH from the app writes its palette to the light, and
`StateTileEffect` reads it straight back. `MatrixLight.get_effect()` slices
`palette[:palette_count]`, so the values that come back are the app's own, with
brightness and kelvin intact.

The sweep drives the Android app over adb: tap `theme_button`, pick a theme, tap
`save_button` (the palette does not reach the device until Save), wait, then
read the light over the LAN.

## Files

| File | Contents |
| --- | --- |
| `themes.jsonl` | 179 records: name, category, picker index, palette |
| `picker-order.txt` | Picker contents in order, including the 11 category headings |
| `tools/enumerate_themes.py` | Scrolls the picker and lists every entry |
| `tools/sweep_themes.py` | Drives the app and captures each palette |
| `tools/analyse_themes.py` | Diffs the capture against `library.py` |

Run the tools from this directory with a light already running MORPH:

```bash
./tools/sweep_themes.py --ip 192.168.1.100 --names picker-order.txt
./tools/analyse_themes.py
```

## What the capture found

Of the 27 themes sharing a slug with the library: 2 are identical, 6 differ only
by a uniform brightness scale of ×1.1087, and 19 are genuinely redefined —
different hues, different colour counts, and in `soothing` a kelvin change from
3500 to 8000. 146 app themes are absent from the library. 30 library keys have
no app counterpart, some of which are renames rather than removals: the app
spells it `Forrest 🌳`, and uses `Aurora 🌌` where the library has
`aurora_borealis`.

That ×1.1087 is 1/0.902, and 0.902 is 230/255. Whatever source the library was
transcribed from capped brightness at 230 of 255 while the app sends a peak of
full, so those six are the same palette at a different level rather than a
changed theme.

## Caveats

**Palette order is meaningless.** The app shuffles the order on every
application — the same theme applied twice returns the same colours in a
different sequence. Compare as an unordered set.

**Sixteen-colour palettes may be truncated.** 21 themes returned exactly 16
colours, the protocol's palette ceiling. A theme defining more would be clipped
to exactly 16, and this method cannot tell a clipped palette from one that
genuinely has 16.

**Six slugs collide**, mostly AFL against NRL clubs with genuinely different
palettes: `brisbane`, `melbourne`, `sydney`, `gold_coast`, `new_zealand`.
`christmas` collides too (Holidays against Archives) but both carry identical
palettes, so it collapses cleanly.

**Captured with one product.** All readings came from a LIFX Tile (product 55).
The palette is effect configuration rather than rendered output, so it should
not vary by product, but that is untested.
