# Fallout effects on the delivered badge

The four controllable case LEDs are white, not RGB. The separate red indicator
is not controlled by Fallout; the firmware reported charging while connected.

Decorative lights default to Off. When enabled, Fallout keeps slow white waves
running on every page after its startup sweep.
The delivered firmware uses a nonlinear brightness curve: the old Low limit
(0.12) produced less than 1% PWM duty. Fallout now uses limits
0/0.35/0.60/0.85 for Off/Low/Medium/Bright, retaining low-battery dimming.
Change these in **STAT → PROFILE → LIGHTS / REMINDERS**:

- **Decorative lights Off:** stop ambient animation; reminder pulses may still occur.
- **Brightness Off:** stop all case lights, including reminder pulses.
- **Reminders Off:** stop automatic reminder cards and their light pulses.

Only **Color and Shaded** Vault Boy remain, each in green and gold themes.
Older Outline saves migrate to Color without deleting progress.

**Pixel Glow is removed**, along with its controls. Text stays crisp regardless
of a legacy saved glow preference. Pixel and Vector fonts remain available.

**CRT SWEEP** toggles a 12-row translucent band moving about three times faster than the original. The band is drawn
after all text and artwork so it covers the entire screen without missing pixel rows. The
initial fixed scanline overlay was rejected during physical review and removed.
The browser's CRT switch can also suppress its preview effects.

## Validation and preservation

The case-light run was measured on the actual device for 26 seconds and visually
confirmed by the user. All four appearances rendered successfully. Regression
checks verify that obsolete glow preferences cannot restore halos and that the
moving overlay renders after every content layer.

The crisp-text revision passed 210 Python tests, both JavaScript suites and all
nine browser tests. Hardware validation and preservation logs are private under
`.local/fallout-effects-2026-10-27/`.

Only Fallout was updated. Hash checks protect the stock USB files, both secrets
files, and the installed Trail and Portal files. The previous Fallout app
versions and original Fallout save remain backed up locally.

The sweep lasts about 2.75 seconds, then stays off for a random 20–45 seconds
measured from the end of the pass. It never wraps directly into another pass.
During the pause its render state stays fixed, so it does not force extra
framebuffer redraws. This limits CRT-related work; it is not a battery-life
measurement, and other app animations still run. Decorative lights default to
Off for fresh settings; saved explicit preferences remain available.

## Automatic battery saver

Below 10% charge, Fallout displays **ECO**, caps the backlight at 20% (never
brightening a dimmer setting), stops CRT and all case LEDs, freezes decorative
animation, limits automatic redraw checks to twice per second, and polls sensors
every 30 seconds (five seconds while viewing Sensors). Buttons redraw immediately;
clock, focus timer, saving, and on-screen reminders continue. The battery is checked
every ten seconds. Normal operation returns at 12% to prevent repeated switching.
An unavailable battery reading retains the current mode. Saved lighting and CRT
preferences are preserved. Normal backlight brightness returns on recovery or
normal app exit; the stock brightness preference is never written. Recovery starts
a full new random 20–45 second CRT pause. The browser preview also shows all four
case LEDs off in ECO, including while a reminder card remains open.

Held directional controls keep their normal repeat delay after a slow frame;
missed repeats do not cause a burst through lists or across the map.

This reduces activity but does not establish an all-day battery runtime. Battery
percentage is the firmware's voltage-based estimate.

At the bottom of STAT → PROFILE: **Created with AI by DChevrier1**.

The final overlay/power revision passed 213 Python tests, both JavaScript test
suites, and all nine browser tests. Its physical-device verification uses injected
battery readings to exercise actual backlight and LED behavior; it does not claim
a discharge-duration test. Logs and rollback copies stay local and unpublished.
