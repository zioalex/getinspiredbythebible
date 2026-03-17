# Play Store Assets

This directory holds all assets required for a Google Play Store listing.

## Files

| File | Dimensions | Status | Notes |
|------|-----------|--------|-------|
| `ic_launcher_store_512.png` | 512 × 512 | ✅ Generated | Hi-res app icon (required) |
| `feature_graphic_1024x500.png` | 1024 × 500 | ✅ Generated | Feature graphic (required) |
| `screenshots/*.png` | 1080 × 1920 (min) | ⏳ Needed | Phone screenshots (min 2, max 8) |

## Regenerating icons

Run the generation script from the `android/` directory:

```bash
python3 scripts/generate_icons.py
```

The script reads the vector drawable design from:

- `app/src/main/res/drawable/ic_launcher_foreground.xml`
- `app/src/main/res/drawable/ic_launcher_background.xml`

It also writes mipmap PNG icons directly into the `res/` tree:

| Density | Folder | Size |
|---------|--------|------|
| mdpi | `mipmap-mdpi/` | 48 × 48 |
| hdpi | `mipmap-hdpi/` | 72 × 72 |
| xhdpi | `mipmap-xhdpi/` | 96 × 96 |
| xxhdpi | `mipmap-xxhdpi/` | 144 × 144 |
| xxxhdpi | `mipmap-xxxhdpi/` | 192 × 192 |

## Screenshots

Screenshots must be **actual app screenshots** taken from a running device or emulator.

### Steps to capture

1. Launch the app on a **Pixel 6** (or similar) emulator — profile size 1080 × 2400.
2. Navigate to each key screen:
   - **Home / Chat** — main conversation view
   - **Bible Reader** — passage display with verse highlighting
   - **Search** — search results list
   - **Settings** — theme/language options
3. Use **Android Studio → Device Manager → Screenshot** (camera icon) to save each
   screenshot as a PNG.
4. Place PNGs in `play_store_assets/screenshots/` named descriptively,
   e.g. `01_chat.png`, `02_bible_reader.png`, etc.

### Minimum requirements

- At least **2** phone screenshots required for Play Store submission.
- Accepted sizes: **1080 × 1920** or any **9:16** ratio (landscape 1920 × 1080 also
  accepted but portrait is preferred for phone listings).
