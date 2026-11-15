# DEMO VIDEO: TRIAGE — AI air defense for small outposts

**Length:** 75–90 seconds. **Tone:** calm, realistic, tense but not dramatic.
No explosions, no gore, no real unit insignia.

**The interceptor is a real CAD model.** Launches, intercepts and the bench swap are rendered in
3D from our own GLB, cut against the live tablet screen. Keep the hardware shots restrained and
documentary — a small drone leaving a rack at night, not an action sequence. Intercepts land as
a clean disappearance, not a fireball.

**Source material:** every screen below is the real software. Run it with the **RUN FULL DEMO**
button and it plays this exact sequence hands-free, so the tablet can be screen-captured
directly rather than mocked up. Timings in brackets are the app's own sim clock.

---

## SETTING

Night. A small remote desert outpost ("FOB Juniper," fictional). Inside a cramped Base Defense
Operations Center: one watch officer in plain uniform, a rugged tablet running Triage, a radio,
a coffee cup. Outside: a rack of 4 small interceptor drones under a shelter.

Interface is warm charcoal and bone-white. Green = friendly or ready, amber = unknown or
pending, red = threat, grey-taupe = decoy.

---

## SCENE 1 — Standby (0:00–0:10)

Wide shot of the quiet outpost at night. Cut to the watch officer glancing at the tablet.

On screen: the outpost perimeter with labelled zones — HOUSING, COMMS, GENERATOR, CLINIC,
PARKING, FUEL, RADAR, OPS — the high-value ones outlined in amber. The interceptor rack sits
inside the wire. Header reads **FOB JUNIPER · WATCH OFFICER STATION**, a live clock, and a
green **ARMED · MONITORING** pill. Footer: **PERIMETER SECURE**.

The rack shows 4 units: **Unit 1** large, with a live attitude horizon, **15.8 V · 100%**,
Variant A, READY. Units 2–4 below it: Var A, Var B, Var A.

> **VO:** "Small outposts like this one have no air defense crew. Just one person on watch."

---

## SCENE 2 — Contact (0:10–0:24)

Tablet chimes softly. Tracks appear at the perimeter edge. Close-up of the officer leaning in.

- **[t+2]** Green tag: **F1 · FRIENDLY — "Registered return flight."**
- **[t+5]** Amber tag: **A · UNKNOWN — "Classifying…"**
- **[t+8]** Second amber tag: **B · UNKNOWN**, resolving to red **THREAT — "High confidence ·
  heading for housing"** with a countdown **ETA 0:18**.

Cut to the TRACKS rail. Each track carries a visible score and the reasoning behind it:

```
B · THREAT                    96
+35 heading to housing
+25 steady path
+20 speed match
+20 unregistered
```

> **VO:** "Triage scores every track and shows its work. The officer can see exactly why
> something was called a threat."

---

## SCENE 3 — Triage recommends (0:24–0:38)

The plan panel, headed **TRIAGE · RECOMMENDED PLAN**:

```
Unit 1 (Variant A) → Track A      launch early
Unit 3 (Variant B) → Track B      engage · threat
DECISION WINDOW — LAUNCH EARLY, DECIDE ON APPROACH
```

- **[t+6.9]** Unit 1 is sent out early against the still-unknown track.
- **[t+9.9]** Track B is moving too fast for a Variant A. Only the rack's single **Variant B**
  can catch it, so Triage assigns **Unit 3**.

The officer taps the large **APPROVE** button. It flashes **APPROVED ✓**.

**Cut to 3D:** two interceptors spin up and lift off the rack into the dark. Low angle, close on
the airframe, rotor wash kicking dust off the pad. Hold long enough to read the drone as a real
designed object — this is our hardware, and it is the only time in the film we see it fly.

> **VO:** "Triage recommends. The officer decides. Nothing launches without a human."

---

## SCENE 4 — Decide in flight (0:38–0:54)

Back on the tablet.

- **[t+15.8]** **3D beat:** Unit 3 closes on the incoming drone against the night sky. Cut on the
  moment of contact — no explosion, just both objects gone and empty sky. Back on the tablet,
  Track B's icon is gone. Event log: **"Unit 3 intercepted Track B."** Unit 3's card flips to
  **EXPENDED · SLOT EMPTY**.
- **[t+21.8]** Track A's tag sharpens to grey: **DECOY — "Erratic path · no asset targeted."**
  A new plan line appears: **Unit 1 → Track A · return — "now likely decoy."** Officer approves.
- **[t+34]** **3D beat:** Unit 1 banks away from the decoy and settles back onto its pad, intact.
  Tablet reads **RETURNING**, then **READY**. Event log: **"Unit 1 returned, not expended."**
  This shot is the thesis of the whole product — let it breathe.

> **VO:** "Interceptors go out early, but Triage only commits at the last moment. When a track
> turns out to be a decoy, the interceptor comes home. Decoys don't drain the rack."

---

## SCENE 5 — The gap (0:54–1:08)

A new track crosses the perimeter, moving noticeably faster than the others.

- **[t+51.9]** The plan panel turns red:

```
NO CAPABLE UNIT ON RACK
faster than Variant A · only Variant B unit already expended
Track C at 40 · needs 48 · rack tops out at 30
```

- A full-width red banner: **ALERT · personnel near parking take cover.** The PARKING zone
  pulses on the map.
- **"Unit 4 launched (best effort)"** — shown honestly, not as a save.
- **[t+56.7]** **3D beat:** Unit 4 chasing, falling behind, the faster track pulling away out of
  frame. Event log: **"could not match speed."**
- **[t+64.9]** **IMPACT · parking area. No personnel. Logged as capability gap.**

Hold on the officer's face. No music sting.

> **VO:** "Triage had the right interceptor for this threat. It had already spent it. It says so,
> protects people first, and logs what it was missing."

---

## SCENE 6 — Morning after (1:08–1:22)

Cut to daylight. The after-action report is open on the tablet:

```
TRACKS DETECTED 4      DECOYS IDENTIFIED 1
THREATS INTERCEPTED 1  BEYOND RACK CAPABILITY 1
```

Below it, the Velocity card:

> **Reconfigure 1 unit: swap the rotor kit. Core and software unchanged.**
> `CORE · REUSED 80% / SWAPPED 20%`
> *Built with Kearney Velocity AI*

**Cut to 3D, the money shot:** the interceptor on a bench, exploded-view. The shared core —
flight controller, ESCs, radio, airframe — holds still and stays lit. The swappable modules —
motors, props, battery — lift away in one colour and the Variant B parts drop in. The model
reassembles. Same core, different capability. Then a short live-action insert of a technician's
hands doing the same swap, to ground it.

Back on the tablet, Unit 1 reads **RECONFIG (A → B)**, then **Unit 1 · Variant B · READY**.

> **VO:** "Every interceptor shares one core. Velocity tells us which modules to change. The
> swap takes minutes, between attacks — not during one."

---

## SCENE 7 — Night 2 (1:22–1:32)

Night again. The same kind of fast track crosses the wire.

The plan panel reads **Unit 1 (Variant B) → Track T1 · engage**. One tap.
**3D:** Unit 1 launches and closes fast this time — same airframe, visibly quicker, and it keeps
up. **[t+9.9]** Event log: **"Unit 1 intercepted Track T1."** The map clears.

> **VO:** "Same threat. Different outcome."

---

## SCENE 8 — Close (1:32–1:40)

Dawn. The officer steps outside and looks at the quiet outpost.

Title card:

> **TRIAGE — the right interceptor for every threat.**
> *Built with Kearney Velocity AI*

---

## Notes for the editor

- **The tablet footage is real.** Press RUN FULL DEMO and screen-record; every string above is
  what the software actually prints. Nothing needs to be faked or re-created.
- **Unit 1 is a real drone.** Its battery voltage, percentage and attitude horizon on screen are
  live telemetry over USB from an actual flight controller. Worth one insert shot of the physical
  drone next to the tablet, tilting it and showing the horizon follow.
- **The 3D model is the one we actually designed and built.** The GLB, the physical drone on the
  desk and the Variant B BOM are the same airframe, so the launch shots, the exploded-view swap
  and the hardware on the table should all read as one object. Match the 3D lighting to the night
  palette of the UI rather than a studio look.
- **Variant A and Variant B must be visually distinguishable** in the 3D — different motors and
  props, same core — or the night 2 payoff doesn't land.
- **Night 1 runs about 70 seconds of sim time.** If the cut needs to be tighter, the safe
  compressions are: the quiet stretch between the recall (t+34) and the fast threat (t+52), and
  the after-action hold.
- **Keep the capability gap honest.** The impact is the point of the film — it is what motivates
  the swap. Don't cut it or soften it.
- **Colour meanings must stay consistent** with the UI: green friendly/ready, amber
  unknown/pending, red threat/alert, grey-taupe decoy.
