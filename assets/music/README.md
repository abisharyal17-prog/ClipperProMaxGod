# Music

Background beds used by the render stage. Reference a track by name in
`clips.json` (`"music": "my-track"`) or via the render node's `default_music`;
the renderer resolves `assets/music/<name>.mp3`.

## Dropping in tracks

- Put `.mp3` files directly in this folder. The filename (without extension) is
  the name you reference.
- Music is looped to the clip length, trimmed, mixed under the voice, and ducked
  with `sidechaincompress` when `duck_music` is on. Tune the bed with the render
  node's `music_volume` parameter (default `0.18`).
- Absolute paths also work if you keep a personal library outside the repo.

## Licensing

Only ship audio you are legally allowed to redistribute. Podsafe / royalty-free
libraries (e.g. tracks you have licensed or produced yourself) are fine; most
commercial music is **not**. When in doubt, leave it out of version control and
point the `music` field at an absolute path on your own machine.

## `test-bed.mp3`

This file is a **generated placeholder** used by the smoke tests — it is not a
real music track and carries no licensing concern. Replace it with your own
cleared audio for real projects, or ignore it entirely.
