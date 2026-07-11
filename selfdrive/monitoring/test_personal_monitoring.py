import pytest

from cereal import car, log
from openpilot.common.realtime import DT_DMON
from openpilot.selfdrive.monitoring.policy import DriverMonitoring
from openpilot.selfdrive.monitoring.test_monitoring import msg_ATTENTIVE, msg_DISTRACTED
from openpilot.selfdrive.selfdrived.events import EVENTS
from openpilot.sunnypilot.selfdrive.selfdrived.events_base import ET, Priority


AlertLevel = log.DriverMonitoringState.AlertLevel
AlertSize = log.SelfdriveState.AlertSize
AlertStatus = log.SelfdriveState.AlertStatus
AudibleAlert = car.CarControl.HUDControl.AudibleAlert
VisualAlert = car.CarControl.HUDControl.VisualAlert
EventName = log.OnroadEvent.EventName


def run_frame(dm, driver_state):
  """Feed one synthetic 20 Hz model frame through the monitoring feedback loop."""
  dm._update_states(
    driver_state=driver_state,
    cal_rpy=[0.0, 0.0, 0.0],
    car_speed=30.0,
    op_engaged=True,
    standstill=False,
  )
  dm._update_events(
    driver_engaged=False,
    op_engaged=True,
    standstill=False,
    wrong_gear=False,
  )
  return dm.alert_level


def run_seconds(dm, driver_state, seconds):
  return [run_frame(dm, driver_state) for _ in range(round(seconds / DT_DMON))]


def first_level_time(levels, level):
  try:
    # Each result is recorded after processing its frame.
    return (levels.index(level) + 1) * DT_DMON
  except ValueError:
    return None


def test_requires_continuous_distracted_sequence():
  dm = DriverMonitoring()
  required = dm.settings._DISTRACTED_VALID_FRAMES

  for _ in range(required - 1):
    run_frame(dm, msg_DISTRACTED)

  assert not dm.driver_distracted
  assert dm.awareness == 1.0

  run_frame(dm, msg_ATTENTIVE)
  assert dm._distracted_valid_frames == 0

  for _ in range(required):
    run_frame(dm, msg_DISTRACTED)

  assert dm.driver_distracted
  assert dm.awareness < 1.0


def test_closed_loop_alert_schedule_and_recovery():
  dm = DriverMonitoring()

  # Run long enough to pass validation and traverse all three alert levels.
  levels = run_seconds(dm, msg_DISTRACTED, 24.0)
  assert first_level_time(levels, AlertLevel.one) == pytest.approx(7.0, abs=DT_DMON)
  assert first_level_time(levels, AlertLevel.two) == pytest.approx(11.0, abs=DT_DMON)
  assert first_level_time(levels, AlertLevel.three) == pytest.approx(23.0, abs=DT_DMON)

  # A terminal alert remains latched until disengagement.
  run_seconds(dm, msg_ATTENTIVE, 2.0)
  assert dm.alert_level == AlertLevel.three

  dm._update_events(
    driver_engaged=False,
    op_engaged=False,
    standstill=False,
    wrong_gear=False,
  )
  assert dm.alert_level == AlertLevel.none
  assert dm.awareness == 1.0


def test_slower_awareness_step():
  dm = DriverMonitoring()
  assert dm.step_change == pytest.approx(DT_DMON / 22.0)


def test_level_two_events_are_visual_only():
  distracted = EVENTS[EventName.driverDistracted2][ET.PERMANENT]
  unresponsive = EVENTS[EventName.driverUnresponsive2][ET.PERMANENT]
  assert distracted.audible_alert == AudibleAlert.none
  assert distracted.alert_size == AlertSize.small
  assert distracted.alert_status == AlertStatus.normal
  assert distracted.priority == Priority.LOW
  assert distracted.visual_alert == VisualAlert.none
  assert unresponsive.audible_alert == AudibleAlert.none
  assert unresponsive.alert_size == AlertSize.small
