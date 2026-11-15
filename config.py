import os

SERIAL_PORT = os.environ.get("TRIAGE_PORT")  # None = autodetect first /dev/cu.usbmodem* (Windows: set COM3)
USE_MOCK = os.environ.get("TRIAGE_MOCK", "1") == "1"  # default MOCK. Live needs TRIAGE_MOCK=0
# Motors NEVER default on. Approve will not spin hardware unless a human sets TRIAGE_MOTORS=1.
MOTORS_ENABLED = os.environ.get("TRIAGE_MOTORS", "0") == "1"

MAP_W, MAP_H = 1000, 700  # map units, shown as meters
TICK_HZ = 10
DT = 0.1  # fixed sim step, seconds

VARIANTS = {  # speeds are map units per second, tuned for demo pacing
    "A": {"speed": 30, "max_range": 1500, "cost": 2000},
    "B": {"speed": 60, "max_range": 1400, "cost": 5000},
}
ASSET_VALUE = {"housing": 1.0, "generator": 0.8, "comms": 0.7, "fuel": 0.7, "parking": 0.4}

BATTERY_V_MIN, BATTERY_V_MAX = 13.2, 16.8  # 4S. CONFIRM the pack at gate H1.
MOTOR_TEST_VALUE = 1080
MOTOR_HARD_CAP = 1100  # enforced in bridge code, not just here
MOTOR_TEST_SECONDS = 1.0
# 0-based MSP motor indices to spin during motor_test. Motor 2 (index 1) skipped (bad ESC/connection).
MOTOR_TEST_INDICES = (0, 2, 3)  # motors 1, 3, 4

THREAT_HIGH, THREAT_LOW = 70, 40
LABEL_HYSTERESIS = 3  # must cross a threshold by this much to change label
SCORE_TAU = 1.0  # seconds, smoothing time constant
NEW_CONTACT_SECONDS = 2.0  # label is "unknown" until this much track history exists
HISTORY_DT, HISTORY_LEN = 0.5, 12  # 6 s heading window
HEADING_CONE_DEG = 20
STEADY_FULL_DEG, STEADY_ZERO_DEG = 5, 40
ATTACK_SPEED_MIN, ATTACK_SPEED_MAX = 15, 45

CAPABLE_SPEED_MARGIN = 1.2
FORCE_COMMIT_ETA = 8
DECOY_RECALL_HOLD = 3
STANDOFF_RADIUS = 60
INTERCEPT_RADIUS = 15
