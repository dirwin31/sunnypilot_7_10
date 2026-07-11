# sunnypilot on a 2026 Honda Civic Hybrid — What's Adjustable

A map of what can be improved/tuned for the 2026 Civic Hybrid on this sunnypilot
repo. Understanding-first: no changes are implied by this document.

> **Safety note:** Everything below changes how a ~2-ton car behaves on the road.
> Understand it first, keep hands on the wheel and eyes on the road, and test any
> change somewhere safe.

## 1. How your car is seen by the software

The 2026 Civic Hybrid (sedan and hatchback) is officially supported and maps to
the `HONDA_CIVIC_2022` platform — a **Bosch radarless** car.
(`opendbc_repo/opendbc/car/honda/values.py:208-212`)

Consequences:

- **Camera-only, no radar** — `honda/interface.py:51` (`ret.radarUnavailable = True`).
  All distance-keeping comes from the camera + vision model, not radar.
- **Hybrid auto-detected** on the CAN bus — `honda/interface.py:74` (message
  `0x184` sets the `HYBRID` flag). Automatic, not configured.

## 2. Steering / lateral control — the biggest lever

**a) Tuning model (code-level).** Today the platform uses classic **PID** steering
(`honda/interface.py:113-116`). sunnypilot also ships a purpose-trained
**Neural Network Lateral Control (NNLC)** model for this exact car:
`sunnypilot/neural_network_data/neural_network_lateral_control/HONDA_CIVIC_2022.json`.
NNLC generally gives smoother curve-handling and better centering than PID.
UI toggle: **Settings → "Neural Network Lateral Control (NNLC)"**.

**b) Torque params (UI).** `steering_sub_layouts/torque_settings.py` —
"Customize Torque Params" and "Enforce Torque Lateral Control." Adjust steering
strength/response without editing code.

**c) Behavior toggles (UI):**
- **MADS** (Modular Assistive Driving System) — decouples steering assist from
  cruise so lane-keeping stays on when you tap the brake.
  `steering_sub_layouts/mads_settings.py`.
- **Pause Lateral with Blinker** + post-blinker delay — stops fighting you during
  lane changes.
- **Customize Lane Change** — auto lane change, speed thresholds, etc.

## 3. Gas/brake — longitudinal control

Because it's radarless, this is the most consequential area, with a safety
tradeoff baked into the code:

```python
# honda/interface.py:53-54
# Disable the radar and let openpilot control longitudinal
# WARNING: THIS DISABLES AEB!
```

Enabling **openpilot longitudinal** ("alpha long") hands gas/brake to the vision
model but **turns off Honda's stock automatic emergency braking**. Stock
(`pcmCruise`) longitudinal keeps AEB but is less customizable. That's the core
decision — understand it before flipping it.

Related: **Dynamic Experimental Control (DEC)** — auto-switches between chill and
experimental longitudinal modes based on driving conditions.

## 4. Speed control

- **Smart Cruise Control – Map** and **– Vision** (`cruise_sub_layouts/`) —
  auto-adjust set speed for curves (vision) and mapped speed limits/turns (map/OSM).
- **Speed Limit Control** with policy + offsets.
- **Custom ACC Speed Increments** — how much a short vs. long press of +/- changes
  set speed.

## 5. An empty canvas

`selfdrive/ui/sunnypilot/layouts/settings/vehicle/brands/honda.py` is a stub
(`update_settings` just `pass`). If you ever want Honda-specific toggles surfaced
in the UI, that's where they'd go.

## Suggested first deep-dive

**Steering.** NNLC vs. PID is the highest-value, lowest-risk improvement, and the
NNLC model already exists for this car.
