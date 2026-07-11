# Driver Monitoring Tuning Notes

This SunnyPilot checkout no longer uses the two paths originally referenced:

- `selfdrive/monitoring/driver_monitor.py` has moved to `selfdrive/monitoring/policy.py`.
- `selfdrive/controls/lib/events.py` has moved to `selfdrive/selfdrived/events.py`.

There is no `VISION_TURN_COUNT` in this version. Its replacement is a combination of input filtering and awareness timeouts.

> [!WARNING]
> Changes that delay driver-inattention intervention or silence urgent on-road warnings weaken a safety mechanism. The information below maps the control flow and supports safe offline experimentation; it does not provide a production patch that suppresses those protections.

## 1. Temporal filtering

The raw distracted result is calculated and filtered in `selfdrive/monitoring/policy.py`:

- Raw classification: line 269
- Filter update: line 271
- Filter time constant: line 71
- State thresholds: lines 320 and 334

```python
self._DISTRACTED_FILTER_TS = 0.25
```

This feeds:

```python
self.driver_distraction_filter = FirstOrderFilter(
  0., self.settings._DISTRACTED_FILTER_TS, DT_DMON
)
```

At `DT_DMON = 0.05`, the filter runs at 20 Hz. Increasing `_DISTRACTED_FILTER_TS` makes transitions slower, but it is not a strict consecutive-frame validator: prior samples decay rather than resetting.

Actual consecutive counters in this area are:

```python
self._DCAM_UNCERTAIN_ALERT_COUNT = int(60 / DT_DMON)
self._DCAM_UNCERTAIN_RESET_COUNT = int(2 / DT_DMON)
self._HI_STD_FALLBACK_TIME = int(10 / DT_DMON)
self._POSE_OFFSET_MIN_COUNT = int(60 / DT_DMON)
self._WHEELPOS_FILTER_MIN_COUNT = int(15 / DT_DMON)
```

These govern camera uncertainty, policy fallback, and calibration—not the ordinary distracted-alert sequence.

## 2. Awareness decay

There is no independent fixed decrement constant. The decrement is `step_change`:

```python
self.awareness = max(self.awareness - self.step_change, -0.1)
```

This occurs at `selfdrive/monitoring/policy.py:341`.

It is derived from the terminal timeout:

```python
self.step_change = DT_DMON / self.settings._VISION_POLICY_ALERT_3_TIMEOUT
```

or:

```python
self.step_change = DT_DMON / self.settings._WHEELTOUCH_POLICY_ALERT_3_TIMEOUT
```

These calculations are in `selfdrive/monitoring/policy.py:182-193`.

Current schedules are:

```python
# Face detected, vision monitoring
self._VISION_POLICY_ALERT_1_TIMEOUT = 3.
self._VISION_POLICY_ALERT_2_TIMEOUT = 5.
self._VISION_POLICY_ALERT_3_TIMEOUT = 11.

# No reliable face, wheel-touch fallback
self._WHEELTOUCH_POLICY_ALERT_1_TIMEOUT = 15.
self._WHEELTOUCH_POLICY_ALERT_2_TIMEOUT = 24.
self._WHEELTOUCH_POLICY_ALERT_3_TIMEOUT = 30.
```

The alert thresholds are normalized from those same timeouts:

```python
threshold_alert_1 = 1 - alert_1_timeout / alert_3_timeout
threshold_alert_2 = 1 - alert_2_timeout / alert_3_timeout
step_change       = DT_DMON / alert_3_timeout
```

Consequently, independently scaling only `step_change` would make the configured timeout names inaccurate. Any legitimate retuning must treat each three-value schedule as one invariant:

```text
0 < ALERT_1_TIMEOUT < ALERT_2_TIMEOUT < ALERT_3_TIMEOUT
```

Recovery uses the same step multiplied by the recovery factors at `selfdrive/monitoring/policy.py:326`. Reducing `step_change` therefore also slows recovery unless that calculation is redesigned.

## 3. Event mapping

The state-to-event translation occurs in `selfdrive/selfdrived/selfdrived.py:223-239`:

```text
AlertLevel.one   -> driverDistracted1 / driverUnresponsive1
AlertLevel.two   -> driverDistracted2 / driverUnresponsive2
AlertLevel.three -> driverDistracted3 / driverUnresponsive3
```

Their visual and acoustic definitions begin at `selfdrive/selfdrived/events.py:341`.

Each `Alert` ends with:

```python
Priority,
VisualAlert,
AudibleAlert,
duration,
```

Current behavior:

| Level | Size/status | Audible |
|---|---|---|
| 1 | Small, normal, low priority | `none` |
| 2 | Mid, user prompt, medium priority | `promptDistracted` |
| 3 | Full, critical, high priority | `warningImmediate` |

Level 1 is already the visual-only text tier:

```python
AlertStatus.normal, AlertSize.small,
Priority.LOW, VisualAlert.none, AudibleAlert.none, .1
```

A status bar is not a distinct event property in this event system. The closest representation is `AlertSize.small` with `Priority.LOW`, `VisualAlert.none`, and `AudibleAlert.none`.

Level 3 also activates deceleration independently of the event presentation in `selfdrive/controls/controlsd.py:215`:

```python
cs.forceDecel = (
  driverMonitoringState.alertLevel == AlertLevel.three
  or selfdriveState.state == State.softDisabling
)
```

Editing `events.py` would not remove that response.

Finally, mici hardware overrides level-1 and level-2 definitions at `selfdrive/selfdrived/events.py:859`, so presentation changes made only to the primary mapping would not apply consistently on that hardware.

## Safe offline evaluation

Inject a custom `DRIVER_MONITOR_SETTINGS` instance into `DriverMonitoring(settings=...)` in `selfdrive/monitoring/test_monitoring.py`, then run:

```sh
pytest -q selfdrive/monitoring/test_monitoring.py
```

This permits measuring transition timing without altering the production on-road policy.
