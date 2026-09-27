# Fonts

Caption and title fonts burned in by libass. Caption presets in `app/config.py`
reference these families by name (e.g. `Montserrat`, `Anton`, `Inter`), and the
render filter passes this folder as `fontsdir`.

All fonts here are **static instances** — libass renders only the default instance
of a variable font, which would otherwise come out too thin — and all are free for
commercial use.

| File                    | Family        | Weight | Used by preset(s)             |
| ----------------------- | ------------- | ------ | ----------------------------- |
| `Anton-400.ttf`         | Anton         | 400    | `beast`, default title font   |
| `ArchivoBlack-400.ttf`  | Archivo Black | 400    | `neon`                        |
| `Bangers-400.ttf`       | Bangers       | 400    | (library)                     |
| `BebasNeue-400.ttf`     | Bebas Neue    | 400    | (library)                     |
| `Inter-700.ttf`         | Inter         | 700    | `dynamic-minimal`, `clean`    |
| `LuckiestGuy-400.ttf`   | Luckiest Guy  | 400    | (library)                     |
| `Montserrat-900.ttf`    | Montserrat    | 900    | `hormozi`, `karaoke`          |
| `Oswald-600.ttf`        | Oswald        | 600    | (library)                     |
| `Poppins-700.ttf`       | Poppins       | 700    | (library)                     |
| `Roboto-900.ttf`        | Roboto        | 900    | (library)                     |

## Licences

- **Anton, Archivo Black, Bebas Neue, Inter, Montserrat, Oswald, Poppins,
  Roboto, Luckiest Guy** — SIL Open Font License 1.1 (OFL).
- **Bangers** — SIL Open Font License 1.1 (OFL).

Both OFL and Apache-2.0 permit bundling and commercial use. If you add a font,
confirm its licence allows redistribution; do not ship proprietary fonts.

## Refreshing

`scripts/fetch_fonts.py` clears this folder and re-downloads every font above,
instancing the variable families (Montserrat) locally with `fonttools` so the
family name and weight are preserved:

```
.venv\Scripts\python.exe scripts/fetch_fonts.py
```

Requires `httpx`, `fonttools` and `Pillow` (the `dev` extra pulls in `fonttools`).
