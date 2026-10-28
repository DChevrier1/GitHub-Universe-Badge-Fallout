# Vault Boy artwork

`vault-boy.gif` is the existing Fallout Pip-Boy Vault Boy walking animation,
downloaded unchanged on September 30, 2026 from:

https://github.com/cogilabs/CogiPB3kMkIVOS/blob/main/images/vaultBoy.gif

The source project's attribution identifies the Vault Boy GIF as gameplay-derived
artwork by David Girou:
https://github.com/cogilabs/CogiPB3kMkIVOS/blob/main/ATTRIBUTIONS.md

Vault Boy and Fallout artwork belong to Bethesda/ZeniMax and their respective
rights holders. This image is not original project art and is not relicensed as
open-source code. The source project describes its use as noncommercial fan use;
that statement does not grant ownership or an independent commercial license.

`../mascot.py` contains hardware representations of the same animation.
`tools/build_mascot.py` performs decoding and resolution adaptation. The outline
style extracts the dark strokes; the shaded style retains the original GIF's
transparent background and filled green shading in a 16-color palette. The
power-armor shaded style tints those same original frames amber/gold at render
time. The simulator and badge draw the same stored frames. The unmodified
source GIF remains here for provenance.

## Color animation variant

`vault-boy-color-sheet.png` is an AI-colorized derivative of the eight poses in
the original GIF, created October 2, 2026 with the built-in imagegen tool. It uses
Vault Boy's blue/yellow suit, blond hair, skin tones and brown boots. It is not an
official Bethesda full-color animation. Only Color and Shaded are offered in STAT → PROFILE. Legacy outline
geometry is retained in the sprite data for provenance. Source character rights remain unchanged.

The exact edit prompt and asset provenance are in [COLOR_PROMPT.md](COLOR_PROMPT.md).
`tools/build_mascot.py` converts both source assets into small display runs; the
color version uses a nine-color palette, the original shaded version uses 16
green shades, and the outline follows the selected phosphor. The source files
remain unmodified by that firmware conversion.
