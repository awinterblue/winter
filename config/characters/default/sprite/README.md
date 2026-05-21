# Winter — sprite art

Two layers of sprite images:

- **The default** — `idle.png` (and optionally `listening.png` / `thinking.png`
  / `speaking.png`), placed here by hand. This is Winter's built-in look.
- **A user override** — `custom.png`. Created when someone uses **Settings… →
  Sprite image → Choose image…**. It overrides the default while it exists.
  The **Reset to default** button deletes only `custom.png`, restoring the
  `idle.png` default — the default files are never touched by the UI.

Drop transparent **PNG** images here by hand for the default. Winter looks for
these filenames, one per state:

- `idle.png`      — resting / waiting
- `listening.png` — while it hears you
- `thinking.png`  — while it works out a reply
- `speaking.png`  — while it talks

You don't need all four — one `idle.png` is enough (it's used for every state).

With no images here, Winter draws its built-in animated character.
