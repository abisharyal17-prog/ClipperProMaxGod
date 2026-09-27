# LUTs

Colour grades applied at the render stage via ffmpeg's `lut3d` filter. Reference a
LUT by name in `clips.json` (`"lut": "teal-orange"`) or via the render node's
`default_lut`; the renderer resolves `assets/luts/<name>.cube`.

## Generated grades

These are written by `scripts/generate_luts.py` — self-authored and free of any
licensing questions. They are 33×33×33 `.cube` files.

| Name          | Look                                                        |
| ------------- | ----------------------------------------------------------- |
| `teal-orange` | Cinematic split-tone: warm skin, cool shadows               |
| `warm`        | Gentle warm white balance lift                              |
| `film`        | Lifted blacks, softened highlights, mild desaturation       |
| `fade`        | Matte / faded film look                                     |
| `punch`       | Contrast + saturation boost                                 |
| `vibrant`     | Strong saturation and contrast                              |
| `cool`        | Cool blue cast, slight contrast                             |
| `noir`        | High-contrast monochrome                                    |

Regenerate all of them (overwrites existing files):

```
.venv\Scripts\python.exe scripts/generate_luts.py
```

## Adding your own

1. Drop a `.cube` file into this folder. The filename (without the extension) is
   the name you reference — e.g. `assets/luts/my-grade.cube` → `"lut": "my-grade"`.
2. Prefer 3D LUTs (`.cube` with a `LUT_3D_SIZE` header). ffmpeg's `lut3d` also
   accepts `.3dl`, but only `.cube` is resolved by name here.
3. Make sure you have the right to redistribute any LUT you ship in this repo.
   Commercial LUT packs usually forbid redistribution; keep those out of version
   control and load them from an absolute path instead (the renderer accepts an
   absolute path in the `lut` field).
