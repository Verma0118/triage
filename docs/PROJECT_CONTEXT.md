# TRIAGE: Project Context

Read this first. It explains the hackathon and our project. The build details live in `TRIAGE_BUILD_PLAN.md`.

## 1. The hackathon

**Kearney x PERLab Hackathon**, sponsored by Growth Signals. **November 13-15, 2026.**

- **Kearney** is a global management consulting firm. **PERLab** (Product Excellence and Renewal Lab) is its product development group.
- The judges and mentors are Kearney consultants. They think in terms of **platforming, BOM cost, product development, and business viability.**

### Schedule
| Day | Time | Event |
|---|---|---|
| Fri | 8:00 PM | Velocity AI demo |
| Fri | 8:45 PM | Build begins |
| Sat | 9:00 AM – 11:00 PM | Build time (venue closes 11 PM) |
| **Sun** | **8:30 AM** | **Submissions due** |
| Sun | 9:30 AM – 1:30 PM | Preliminary judging (in rooms) |
| Sun | 3:30 PM | Finalist pitches |
| Sun | 5:00 PM | Awards |

### Tracks
- **Corporate Track 1, Rapid Platforming:** find parts that can be standardized across products. Build a common core platform plus add-on modules.
- **Corporate Track 2, Consumer Insights:** understand what customers actually want.
- **Corporate Track 3, BOM Cost Linkage:** tie bills of materials to spend data to find savings.
- **Startup Track (ours):** a new hardware and/or software startup in any Kearney industry. **We're in Aerospace & Defense.**

### Velocity AI (must be used)
Kearney PERLab's agentic AI tool for product development. Five stages:
1. **Sense:** scans feedback, trends, and signals for opportunities
2. **Generate:** produces concepts, requirements, and product architecture
3. **Simulate:** tests ideas with digital personas
4. **Build:** prototypes and sourcing plans
5. **Validate:** documentation and feasibility

We have full hands-on access this weekend. **Judges built this tool, so visible, real use matters.**

## 2. Our project: Triage

**Tagline:** the right interceptor for every threat.

### Problem
Remote US outposts like Tower 22 get attacked by cheap drones but have no air defense crew, so the watch officer on shift has seconds to tell real threats from decoys and friendlies with only a few interceptors, and a wrong call costs lives.

**Why it's real**
- **Tower 22 (Jan 2024):** soldiers saw the attack drone on radar, dismissed it as birds or trash, and early reports pointed to confusion with a returning US drone. Three soldiers were killed. The Army investigation found it was most likely preventable.
- US forces in Iraq, Syria, and Jordan were attacked **165 times** between Oct 2023 and Feb 2024.
- Drone incursions over US bases rose about **82%** in one year (230 to about 420).
- In Ukraine, small substations made up **58%** of verified energy strikes last winter.

### Who it's for
- **User:** the Base Defense Operations Center (BDOC) watch officer at a small outpost
- **Site:** remote outposts with a few hundred people or fewer and no dedicated air defense unit
- **Buyer:** JIATF-401 and Army counter-drone program offices, buying for many sites
- **Later:** allied small bases, then critical infrastructure

### Solution
An **AI battle manager** for the watch officer, paired with a **family of low-cost interceptors that share one modular core.**
- **Classifies every drone** as threat, decoy, unknown, or friendly using a transparent **threat score** (heading to a high-value asset, steady path, speed match, unregistered)
- **Ranks by priority** (threat score x asset value x urgency)
- **Each interceptor's core reports its real capability** (variant, battery, health)
- **Sends the cheapest interceptor that can actually stop each threat**
- **Unknowns:** an interceptor goes out early, but Triage only commits at the last moment. Confirmed decoy → the interceptor returns unused. Still unsure at the deadline → defaults to threat.
- **The watch officer approves every plan with one tap**
- **Modular hardware:** when a threat exceeds what's on the rack, Triage logs a capability gap. **Velocity** tells us which modules to swap (motors, props, battery, camera) while the core and software stay the same. The swap happens **between attacks**, not during one.

### Three timescales
| When | What | Who |
|---|---|---|
| Seconds | Triage manages the attack with what's on the rack | Watch officer |
| Hours | Swap modules to fix a logged gap | Site technician |
| Weeks | Velocity designs new modules or variants | Us |

**Pitch line:** "Triage handles the attack. Modularity makes sure the next one goes better."

### Emphasis
**About 75% software (Triage), 25% hardware modularity.** Triage is the star. Modularity backs it up.

## 3. Why it fits Kearney
- **Startup Track A&D:** real, current defense problem
- **Platforming (Track 1):** shared core across the interceptor family
- **BOM cost (Track 3):** % of parts reused, cost per kill
- **Velocity AI:** used to build Triage this weekend, and it's how the company keeps designing variants

## 4. Competition
| Player | What they do | What they don't |
|---|---|---|
| DroneShield C2 Tactical | Tablet C2 that shows detections and triggers mostly radio-based defeat | Doesn't decide which interceptor to spend or when |
| Anduril Lattice / Northrop FAAD / BAE BATS | Full battle management | Needs an air defense crew a small outpost doesn't have |
| Perennial, SkyFall, Neros, Anduril Anvil | Interceptor drones | Leave the decision to the operator |
| Dedrone, Intelic | Detection and sensor fusion | Detection-first, not interceptor allocation |

**Our edge:** the decision software and the interceptors are designed together, so Triage knows each unit's real capability and stops the most threats with the fewest drones, run by someone without air defense training.

**Honest limits:** we don't build sensors (we plug into what the site has). Classification v1 is rules-based.

## 5. Business model
- **Site kit:** interceptors + rack + tablet + software license
- **Recurring:** annual license per site + interceptor resupply (used interceptors get reordered)
- **First path:** pilots through DIU / SBIR, then JIATF-401 and Army program offices

## 6. Hardware status
- One interceptor drone, body fully assembled
- **Betaflight** flight controller + ESCs + motors soldered, ready for PID tuning
- Connected over USB for the demo. It **does not fly** in the demo.
- In the demo it's **Unit 1, Variant A**, with live battery, attitude, and ready state. Approving its plan spins its motors (props off). Its craft name changes to Variant B after the swap.
- Variant B exists as a **BOM only** (no CAD)

## 7. Demo (about 3 min)
1. **Tower 22 replay:** friendly stays green, unregistered track flagged
2. **Live hardware:** tilt the drone and Unit 1 moves on screen
3. **Decoy flow:** unknown → launch early → decoy → interceptor returns unused. Real threat → engaged. Approve spins Unit 1.
4. **Unplug battery:** Unit 1 goes not ready, Triage replans
5. **Capability gap:** fast threat → no capable unit → shelter alert → impact at parking (no personnel) → gap logged
6. **Morning after:** after-action → Velocity card → swap Unit 1 to Variant B
7. **Next night:** Unit 1 is now capable and engages
8. **Close**

**Tone for Tower 22:** respectful and factual. No game-style effects on the real map. The map is a simplified schematic based on public reporting.

## 8. Deliverables
1. Triage software (see `TRIAGE_BUILD_PLAN.md`)
2. Tower 22 replay scenario
3. Live interceptor (Unit 1)
4. Modular beat: gap flag, Velocity card, swap
5. BOM: core vs. swappable modules, % reused
6. Color-coded labels on the physical drone
7. Velocity outputs: one slide per stage
8. Pitch deck (10 slides)
9. Demo video (fictional "Outpost Juniper")

## 9. Pitch deck
1. Title
2. Tower 22
3. Problem + stats
4. Who needs it
5. How Triage works
6. **Live demo**
7. Modular core + Velocity swap card
8. Built with Velocity
9. Market, competition, business model
10. Roadmap + close

**Backup slides:** threat score breakdown, three timescales, market sizing, sources.

## 10. Q&A prep
- **Autonomous killing?** No. A human approves every plan.
- **Why shoot decoys?** We don't. Unknowns get an interceptor sent out early, and it comes back if the track is a decoy.
- **How does the drone know it's a decoy?** It doesn't. Triage decides from the ground using site sensors, radio signals, friendly registration, and the interceptor's camera feed.
- **What if the link is jammed?** The commander sets a lost-link policy. Onboard classification is on the roadmap.
- **Doesn't this need a ton of drones?** No. Triage stretches a small rack by holding fire on decoys and recalling launched units.
- **Swap during an attack?** No. Swaps happen between attacks, based on logged gaps.
- **Why not Lattice?** Too heavy for a two-person site, and Triage is tuned to our interceptors' real specs.
- **Decoys with no data?** Rules first, a learned model from logged engagements later.
- **Students building defense C2?** Pilots through DIU / SBIR, security accreditation as a funded milestone.

## 11. Key decisions (locked)
- Name: **Triage**
- Software leads, hardware modularity supports
- Four labels: threat / decoy / unknown / friendly
- Threat score (0-100) with visible factor breakdown, plus a separate priority score
- Simple math only, no trajectory physics
- Variant B = BOM only
- Human approves every plan
- Modular swaps happen between attacks
- Velocity output goes in the deck

## 12. Sources
See `Triage_Sources.pdf`. The most important ones for Q&A are the Tower 22 investigation coverage, the attack and incursion counts, and DroneShield's product page.
