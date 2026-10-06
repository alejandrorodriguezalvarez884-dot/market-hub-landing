---
name: news-covers
description: Draw or redo the library of cover pictures the news section of Market Hub picks from (one scene per sector or Macro, under three lights: bullish, bearish, neutral). Use when the user asks for new news covers, more variety, a new view or scene, to fix or improve one, or says something like "rehaz las portadas de noticias" or "añade más portadas de Energy". The argument is what to draw or change (a scope, a tone, "all", or a description).
---

# The news covers

The news of Market Hub is illustrated from a library, not one picture per item: for each scope
(the eleven sectors and `Macro`) there is a scene, shot from several places, under three lights.
The site gives an item the picture of its scope and of how it reads, and the item's id decides
which view, so an item keeps its picture.

You make that library here, on this machine, as code. The scenes are built from solids with
three.js and rendered by the local Chrome. **No image service and no model on the network is
used, and no picture is taken from anywhere** (the owner ruled Hugging Face and the like out).

Work from `market-hub-landing/`. Everything is in `covers/`:

| File | What it is |
|---|---|
| `covers/stage.js` | The stage every scene stands on: sky, sun, air, ground, materials, the camera's finishing. `TONES` is the three lights |
| `covers/scenes.js` | `SCENES`: one function per scope. It builds the place and returns the camera of each view |
| `covers/render.mjs` | Renders scope x tone x view into `site/public/covers/news/` and writes the index `site/src/lib/news-covers.json` |
| `covers/overview.mjs` | Puts the whole library on two sheets in `covers/out/`, to look it over |

## The rules of the library

- **One style for all of it.** A cinematic, photographic look: real places with nobody in them,
  told by silhouette, haze and light. If you change the look, change it in `stage.js`, for all.
- **The light is the reading, and nothing else is.** Bullish: a low warm sun breaking through.
  Bearish: a cold wet dusk, rain. Neutral: the flat light of an overcast day. Never an arrow, a
  chart, a red or green verdict, a word.
- **The same scene under each light.** A view of a scope is the same place three times; only the
  weather changes. That is what makes the tone legible when two items sit one under the other.
- Nothing in a scene is a real place, a brand, a logo or a person.
- A scene reads at 176 pixels wide, which is how the list shows it: one strong shape, not detail.

## How to work

```bash
make covers ONLY=Energy      # one scope (all its tones and views), with its sheet in covers/out/energy.jpg
make covers                  # the whole library, and the overview sheets
cd covers && node render.mjs --only Energy:bearish:2 --sheet   # one single picture
```

1. Read the scene you will touch in `scenes.js`, and how the others use the stage: `s.box`,
   `s.cyl`, `s.beam`, `s.put`, `s.lamp`, `s.ground`, `s.sunAt`, `mat.*`, and the helpers on top
   (`mast`, `town`, `trees`).
2. Change it. To add a view to a scope, return a third camera for `view === 3` **and** add `3`
   to `VIEWS` in `render.mjs`: every scope then needs one. To add a scope, add its function to
   `SCENES` under the exact name the news uses (the list is `SECTORS` in
   `src/markethub/newswriter.py`).
3. Render it and **look at the sheet** (`covers/out/<scope>.jpg`: tones across, views down).
   Things to catch: a scene that is only a dark mass, a horizon that is a ruled line, lamps blown
   out to white blobs, a ground that mirrors like glass, an indoor scene with rain, a tone you
   cannot tell from another. Fix and render again; three passes is normal.
4. When the scope is right, run `make covers` once for all and look at
   `covers/out/overview-1.jpg` and `-2.jpg`: the set must still look like one photographer's.
5. `make check` in the repo (the site builds with the new index), and update "Dónde estamos" in
   `docs/HANDOFF.md`.

Things the stage already knows, so you do not rediscover them:

- Distances: with the air as it is, things keep their detail to about 150 units and are haze by
  300. A scene's subject belongs between 40 and 200 units from the camera.
- `span` (returned with the camera) is how far the sun's shadows are computed; small scenes
  (a room, a bench) want 40, a district 260.
- A room returns `indoors: true` (no rain on the lens) and takes its tone from its lamps: see
  `ROOM` in `scenes.js`.
- The ground mirrors what stands on it where it is wet; `s.ground(material, size, shine, blur)`.
- The pictures are JPEG, 1280x720 and a 480x270 `-s` for the lists. The library weighs about
  12 MB; a new view of every scope adds 6.

Do not commit or deploy unless the user asks. The pictures are static files of the site: they
go live with `make deploy`.

## Tell the user

In Spanish, briefly: what you drew or changed, and the sheet to look at. Say plainly that these
are scenes rendered by code, not photographs.
