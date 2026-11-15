# DEMO VIDEO: TRIAGE — AI air defense for small outposts

**Length:** ~1:50. **Tone:** calm, realistic, tense but not dramatic.
No explosions, no gore, no real unit insignia.

**The interceptor is a real CAD model.** Launches, intercepts and the bench swap are rendered in
3D from our own GLB, cut against the tablet screen. Keep the hardware shots restrained and
documentary — a small drone leaving a rack at night, not an action sequence. An intercept is a
clean disappearance, not a fireball.

---

## How the tablet footage is made

**The screen is not a mockup.** We screen-record the real software, and it plays itself.

1. Open Triage, press **RUN FULL DEMO**, screen-record until it finishes. One take, ~96 seconds,
   hands-free. It runs night 1, the capability gap, the after-action report, the module swap and
   night 2, approving each decision on a beat so the **APPROVED ✓** flash reads on camera.
2. That recording gets composited onto the tablet in the 3D scene.
3. **Sync reference:** the app prints its own clock in the header — `SIM 11.7 s`. Every mark
   below is **D+**, seconds after RUN FULL DEMO is pressed. The sim clock on screen is the
   ground truth; if a mark drifts, trust the clock in the footage.

**Capture notes:** full-screen the browser so no tabs or address bar are visible, hide the mouse
cursor, and don't touch the machine during the take — any click will stop the demo runner.

---

## SETTING

Night. A small remote desert outpost ("FOB Juniper," fictional). Inside a cramped Base Defense
Operations Center: one watch officer in plain uniform, a rugged tablet running Triage, a radio,
a coffee cup. Outside: a rack of 4 small interceptor drones under a shelter.

Interface is warm charcoal and bone-white. Green = friendly or ready, amber = unknown or
pending, red = threat, grey-taupe = decoy.

---

# PART ONE — THE OPENING (0:00–0:16)

*No demo footage yet. This is the setup, shot and rendered.*

**0:00** Wide shot of the outpost at night. Desert, wire, a few lit structures, nothing moving.
Wind. A generator hum.

**0:05** Inside the BDOC. Tight on the watch officer: one person, a radio, a coffee cup, a
tablet. On the tablet, the Triage map sits idle — the perimeter, the labelled zones, the rack
showing **4 OF 4 READY**, the green **ARMED · MONITORING** pill, a clock ticking.

**0:11** Cut outside to the rack: four interceptors under a shelter, rotors still, in 3D.

> **VO (0:01–0:15):**
> "Imagine you're the only person awake on a small base like this one.
> No air defense crew. No radar operator. Just you, a screen, and a rack of four interceptors.
> When something crosses the wire, you have seconds to decide what it is — and you only get to
> be wrong once."

**0:16** Hard cut to the tablet, full frame. **The demo footage starts here.**

---

# PART TWO — THE DEMO (0:16–1:52)

*One continuous screen recording, composited onto the tablet. 3D cutaways are intercut over it.*

### Contact — D+2 to D+9

| Mark | On screen |
|---|---|
| **D+2.7** | Green tag at the perimeter: **F1 · FRIENDLY — "Registered return flight"** |
| **D+5.7** | Amber tag: **A · UNKNOWN — "Classifying…"** |
| **D+8.7** | Second contact: **B · UNKNOWN**, resolving to red **THREAT — "High confidence · heading for housing"**, countdown **ETA 0:18** |

Push in on the TRACKS rail. Every track shows its score and the reasoning that produced it:

```
B · THREAT                    96
+35 heading to housing
+25 steady path
+20 speed match
+20 unregistered
```

> **VO (0:18–0:30):**
> "Three contacts. One is a registered flight coming home. Two are unknown.
> Triage scores every track and shows its work — where it's heading, how steadily it's flying,
> whether anyone registered it. No black box. The officer can see exactly why something was
> called a threat."

### The plan — D+7 to D+13

| Mark | On screen |
|---|---|
| **D+7.6** | Plan line: **Unit 1 (Variant A) → Track A · launch early** |
| **D+9.1** | **APPROVED ✓** flashes |
| **D+10.6** | Plan line: **Unit 3 (Variant B) → Track B · engage · threat** |
| **D+12.1** | **APPROVED ✓** flashes |

Panel header reads **TRIAGE · RECOMMENDED PLAN**, with the doctrine line
**LAUNCH EARLY, DECIDE ON APPROACH**.

**3D cutaway:** two interceptors spin up and lift off the rack into the dark. Low angle, close on
the airframe, rotor wash kicking dust off the pad. Hold long enough to read the drone as a real
designed object.

> **VO (0:32–0:44):**
> "Triage recommends. It doesn't fire. Every launch waits for a human tap.
> Track B is moving too fast for a standard interceptor, so it assigns the rack's one fast unit.
> The unknown gets an interceptor sent out early — but Triage hasn't committed to anything yet."

### Decide in flight — D+16 to D+35

| Mark | On screen |
|---|---|
| **D+16.5** | **"Unit 3 intercepted Track B."** Unit 3's card flips to **EXPENDED · SLOT EMPTY** |
| **D+22.5** | Track A turns grey: **DECOY — "Erratic path · no asset targeted."** New line: **Unit 1 → Track A · return — "now likely decoy"** |
| **D+24.0** | **APPROVED ✓** |
| **D+34.9** | **"Unit 1 returned, not expended."** Unit 1 back to **READY** |

**3D cutaway at D+16:** Unit 3 closes on the incoming drone against the night sky. Cut on the
moment of contact — no explosion, both objects simply gone, empty sky.

**3D cutaway at D+35:** Unit 1 banks away from the decoy and settles back onto its pad, intact.
*This shot is the thesis of the whole product. Let it breathe.*

> **VO (0:46–1:02):**
> "The threat is intercepted. And the other track? It wanders. It isn't heading for anything.
> Triage calls it a decoy and brings its interceptor home — unused.
> That's the whole idea. Cheap decoys are how these attacks work: send ten, make the defender
> spend ten. Triage goes out early and only commits at the last moment. Decoys don't drain the
> rack."

### The gap — D+50 to D+66

| Mark | On screen |
|---|---|
| **D+50.7** | New contact, visibly faster than the others |
| **D+52.6** | Plan panel turns red: **NO CAPABLE UNIT ON RACK** — *faster than Variant A · only Variant B unit already expended* — *Track C at 40 · needs 48 · rack tops out at 30* |
| **D+52.6** | Full-width red banner: **ALERT · personnel near parking take cover.** PARKING pulses on the map |
| **D+52.6** | **"Unit 4 launched (best effort)"** |
| **D+54.1** | **APPROVED ✓** |
| **D+57.4** | **"could not match speed"** |
| **D+65.6** | **IMPACT · parking area. No personnel. Logged as capability gap.** |

**3D cutaway at D+57:** Unit 4 chasing, falling behind, the faster track pulling away out of
frame.

Hold on the officer's face. No music sting. Let the impact sit.

> **VO (1:06–1:22):**
> "Then something faster comes in. And Triage says the hardest thing a defense system can say:
> there is nothing on this rack that can catch it.
> It had the right interceptor for this. It already spent it.
> So it does the only useful thing left — it tells people where to take cover, launches what it
> has, and says plainly that it won't make it.
> No one is hurt. And the shortfall gets written down."

### Morning after — D+67 to D+81

| Mark | On screen |
|---|---|
| **D+67.5** | After-action report opens: **TRACKS DETECTED 4 · DECOYS IDENTIFIED 1 · THREATS INTERCEPTED 1 · BEYOND RACK CAPABILITY 1** |
| | Velocity card: **"Reconfigure 1 unit: swap the rotor kit. Core and software unchanged."** · `CORE · REUSED 80% / SWAPPED 20%` · *Built with Kearney Velocity AI* |
| **D+76.5** | Overlay closes, Unit 1 shows **RECONFIG (A → B)** |
| **D+81** | **Unit 1 · Variant B · READY** |

Cut to daylight for this section.

**3D cutaway, the money shot:** the interceptor on a bench, exploded view. The shared core —
flight controller, ESCs, radio, airframe — holds still and stays lit. The swappable modules —
motors, props, battery — lift away in one colour and the Variant B parts drop in. The model
reassembles. Same core, different capability. Then a short live-action insert of a technician's
hands doing the same swap.

> **VO (1:24–1:38):**
> "By morning, that gap is a work order.
> Every interceptor we build shares one core. Kearney Velocity AI takes the gap Triage logged
> and tells us which modules to change — motors, props, battery. The flight controller, the
> radio and the software stay exactly as they are. Eighty percent of the drone is reused.
> The swap takes minutes, and it happens between attacks. Never during one."

### Night 2 — D+85 to D+94

| Mark | On screen |
|---|---|
| **D+84.9** | Night again. Same fast profile crosses the wire |
| **D+86.9** | Plan: **Unit 1 (Variant B) → Track T1 · engage** |
| **D+88.4** | **APPROVED ✓** |
| **D+91.8** | **"Unit 1 intercepted Track T1."** Map clears |

**3D:** Unit 1 launches and closes fast this time — same airframe, visibly quicker, and it keeps
up.

> **VO (1:40–1:46):**
> "Next night. Same threat.
> Different outcome."

---

# PART THREE — CLOSE (1:46–1:52)

Dawn. The officer steps outside and looks at the quiet outpost.

Title card:

> **TRIAGE — the right interceptor for every threat.**
> *Built with Kearney Velocity AI*

> **VO (1:47–1:51):**
> "Triage handles the attack. Modularity makes sure the next one goes better."

---

## Notes for the editor

- **The tablet footage is one unbroken take.** Press RUN FULL DEMO and let it run ~96 seconds.
  Every string in the tables above is what the software actually prints — nothing is faked.
- **Timings are measured, not estimated**, but the app's own `SIM` clock in the header is the
  real timecode. Use it to line the 3D cutaways up with the screen.
- **Unit 1 is a real drone.** Its voltage, percentage and attitude horizon are live telemetry
  over USB from an actual flight controller. Worth one insert shot of the physical drone beside
  the tablet, tilting it so the horizon on screen follows.
- **The 3D model is the one we designed and built.** The GLB, the physical drone and the Variant
  B BOM are the same airframe, so the launch shots, the exploded view and the hardware on the
  table should read as one object. Match the 3D lighting to the night palette of the UI rather
  than a studio look.
- **Variant A and Variant B must be visually distinguishable** in the 3D — different motors and
  props, same core — or the night 2 payoff doesn't land.
- **If the cut needs to be tighter**, the safe compressions are the quiet stretch between the
  recall (D+35) and the fast threat (D+51), and the after-action hold (D+68 to D+76). Do not
  compress the recall or the impact.
- **Keep the capability gap honest.** The impact is the point of the film — it is what motivates
  the swap. Don't cut it or soften it.
- **Colour meanings must stay consistent** with the UI: green friendly/ready, amber
  unknown/pending, red threat/alert, grey-taupe decoy.
