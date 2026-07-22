#!/usr/bin/env bash
set -Eeuo pipefail

API_LEVEL="${API_LEVEL:-34}"
SYSTEM_TARGET="${SYSTEM_TARGET:-google_atd}"
SYSTEM_ARCH="${SYSTEM_ARCH:-x86_64}"
AVD_NAME="${AVD_NAME:-dudu7-ci}"
EMULATOR_PORT="${EMULATOR_PORT:-5554}"
BOOT_TIMEOUT_SECONDS="${BOOT_TIMEOUT_SECONDS:-600}"
RESULTS_DIR="${RESULTS_DIR:-ui-test-results}"
DATA_PARTITION_SIZE="${DATA_PARTITION_SIZE:-1536M}"

SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK_ROOT" ]]; then
    echo "ANDROID_SDK_ROOT or ANDROID_HOME must be set" >&2
    exit 2
fi

export ANDROID_SDK_ROOT="$SDK_ROOT"
export ANDROID_HOME="$SDK_ROOT"
export PATH="$SDK_ROOT/platform-tools:$SDK_ROOT/emulator:$SDK_ROOT/cmdline-tools/latest/bin:$PATH"

mkdir -p "$RESULTS_DIR"
EMULATOR_LOG="$RESULTS_DIR/emulator.log"
SDK_LOG="$RESULTS_DIR/sdk-install.log"
AVD_LOG="$RESULTS_DIR/avd-create.log"

SYSTEM_IMAGE="system-images;android-${API_LEVEL};${SYSTEM_TARGET};${SYSTEM_ARCH}"

df -h > "$RESULTS_DIR/disk-before-sdk.txt" 2>&1 || true
echo "Installing Android system image: $SYSTEM_IMAGE"
set +o pipefail
yes | sdkmanager --licenses >/dev/null 2>&1 || true
yes | sdkmanager "platform-tools" "emulator" "$SYSTEM_IMAGE" 2>&1 | tee "$SDK_LOG"
sdk_status=${PIPESTATUS[1]}
set -o pipefail
if [[ "$sdk_status" -ne 0 ]]; then
    echo "sdkmanager failed with status $sdk_status" >&2
    exit "$sdk_status"
fi

df -h > "$RESULTS_DIR/disk-after-sdk.txt" 2>&1 || true
rm -rf "$HOME/.android/avd/${AVD_NAME}.avd" "$HOME/.android/avd/${AVD_NAME}.ini"
mkdir -p "$HOME/.android/avd"

echo "Creating AVD $AVD_NAME"
echo no | avdmanager create avd \
    --force \
    --name "$AVD_NAME" \
    --package "$SYSTEM_IMAGE" \
    2>&1 | tee "$AVD_LOG"

CONFIG_PATH="$HOME/.android/avd/${AVD_NAME}.avd/config.ini"
python3 - "$CONFIG_PATH" "$DATA_PARTITION_SIZE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
partition_size = sys.argv[2]
keys = {
    "hw.keyboard": "yes",
    "hw.gpu.enabled": "yes",
    "hw.gpu.mode": "swiftshader_indirect",
    "disk.dataPartition.size": partition_size,
    "showDeviceFrame": "no",
    "hw.ramSize": "2048",
    "hw.cpu.ncore": "2",
}
lines = path.read_text(encoding="utf-8").splitlines()
filtered = [line for line in lines if line.partition("=")[0] not in keys]
filtered.extend(f"{key}={value}" for key, value in keys.items())
path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
PY
cp "$CONFIG_PATH" "$RESULTS_DIR/avd-config.ini"

df -h > "$RESULTS_DIR/disk-before-emulator.txt" 2>&1 || true

cleanup() {
    set +e
    adb -s "emulator-${EMULATOR_PORT}" emu kill >/dev/null 2>&1
    if [[ -n "${EMULATOR_PID:-}" ]]; then
        kill "$EMULATOR_PID" >/dev/null 2>&1 || true
        wait "$EMULATOR_PID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

echo "Starting emulator on port $EMULATOR_PORT with ${DATA_PARTITION_SIZE} data partition"
"$SDK_ROOT/emulator/emulator" \
    -avd "$AVD_NAME" \
    -port "$EMULATOR_PORT" \
    -no-window \
    -no-snapshot \
    -noaudio \
    -no-boot-anim \
    -gpu swiftshader_indirect \
    -camera-back none \
    -camera-front none \
    -netdelay none \
    -netspeed full \
    >"$EMULATOR_LOG" 2>&1 &
EMULATOR_PID=$!

echo "$EMULATOR_PID" > "$RESULTS_DIR/emulator.pid"
start_epoch=$(date +%s)
booted=false

while (( $(date +%s) - start_epoch < BOOT_TIMEOUT_SECONDS )); do
    if ! kill -0 "$EMULATOR_PID" 2>/dev/null; then
        echo "Emulator process exited before Android booted" >&2
        break
    fi

    state=$(adb -s "emulator-${EMULATOR_PORT}" get-state 2>/dev/null || true)
    completed=$(adb -s "emulator-${EMULATOR_PORT}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    anim=$(adb -s "emulator-${EMULATOR_PORT}" shell getprop init.svc.bootanim 2>/dev/null | tr -d '\r' || true)
    printf '%s state=%s boot_completed=%s bootanim=%s\n' \
        "$(date --iso-8601=seconds)" "$state" "$completed" "$anim" \
        | tee -a "$RESULTS_DIR/boot-status.log"

    if [[ "$state" == "device" && "$completed" == "1" ]]; then
        booted=true
        break
    fi
    sleep 5
done

adb devices -l > "$RESULTS_DIR/adb-devices.txt" 2>&1 || true
ps -ef > "$RESULTS_DIR/processes.txt" 2>&1 || true
df -h > "$RESULTS_DIR/disk-after-emulator.txt" 2>&1 || true

if [[ "$booted" != true ]]; then
    echo "Android emulator did not boot within ${BOOT_TIMEOUT_SECONDS}s" >&2
    tail -n 300 "$EMULATOR_LOG" >&2 || true
    exit 1
fi

echo "Android emulator booted successfully"
adb -s "emulator-${EMULATOR_PORT}" shell input keyevent 82 || true
adb -s "emulator-${EMULATOR_PORT}" shell settings put global device_provisioned 1 || true
adb -s "emulator-${EMULATOR_PORT}" shell settings put secure user_setup_complete 1 || true

APK_PATH="${APK_PATH:?APK_PATH must point to the emulator APK}" \
RESULTS_DIR="$RESULTS_DIR" \
DUDU_WIDTH="${DUDU_WIDTH:-1280}" \
DUDU_HEIGHT="${DUDU_HEIGHT:-720}" \
DUDU_DENSITY="${DUDU_DENSITY:-200}" \
TEST_URL="${TEST_URL:-}" \
PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7}" \
ACTIVITY_NAME="${ACTIVITY_NAME:-com.metrolist.music.MainActivity}" \
scripts/dudu7_ui_smoke.sh
