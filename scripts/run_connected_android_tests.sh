#!/usr/bin/env bash
#
# Bootstrap + run ./gradlew :app:connectedAndroidTest end-to-end.
#
# What this does, in order:
#   1.  Verifies the SDK + cmdline-tools install (fails with clear
#       remediation steps when missing).
#   2.  Creates a headless AVD ("atrium_test") if no AVDs exist yet.
#   3.  Boots the emulator headless (no GUI, no audio, no snapshot).
#   4.  Waits for `sys.boot_completed = 1` via adb.
#   5.  Runs `./gradlew :app:connectedAndroidTest`.
#   6.  Tears the emulator down regardless of success/failure.
#
# Idempotent — re-running with an AVD already created reuses it.
#
# Prerequisite (ONE-TIME, manual user action):
#   Install "Android SDK Command-line Tools (latest)" via either:
#     A.  Android Studio → Settings → Languages & Frameworks →
#         Android SDK → SDK Tools → check "Android SDK Command-line
#         Tools (latest)" → Apply.  Wait for the download to finish.
#     B.  Manual zip from https://developer.android.com/studio
#         (scroll to "Command line tools only"), unzip the
#         cmdline-tools/ folder, rename it to "latest", and place
#         under $LOCALAPPDATA/Android/Sdk/cmdline-tools/.
#   Then run this script.  No further interaction needed.
#
# Usage (from repo root):
#   bash scripts/run_connected_android_tests.sh [--keep-running]
#
# Flags:
#   --keep-running   Don't kill the emulator after tests; useful for
#                    iterative debugging (re-run gradle directly).
#

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SDK_ROOT="${ANDROID_SDK_ROOT:-${LOCALAPPDATA:-$HOME/AppData/Local}/Android/Sdk}"
AVD_NAME="${AVD_NAME:-atrium_test}"
SYSTEM_IMAGE="${SYSTEM_IMAGE:-system-images;android-36;google_apis_playstore;x86_64}"
DEVICE_PROFILE="${DEVICE_PROFILE:-pixel_5}"
BOOT_TIMEOUT_SECONDS="${BOOT_TIMEOUT_SECONDS:-180}"

KEEP_RUNNING=0
for arg in "$@"; do
    case "$arg" in
        --keep-running) KEEP_RUNNING=1 ;;
        *) echo "Unknown flag: $arg" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
# Tool paths
# ---------------------------------------------------------------------------

# Use .bat on Windows (msys/mingw bash), bare on Linux/macOS.
if [[ "$(uname -s)" =~ MINGW|MSYS|CYGWIN ]]; then
    EXE_SUFFIX=".bat"
else
    EXE_SUFFIX=""
fi

AVDMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/avdmanager${EXE_SUFFIX}"
SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager${EXE_SUFFIX}"
EMULATOR="$SDK_ROOT/emulator/emulator${EXE_SUFFIX}"
ADB="$SDK_ROOT/platform-tools/adb${EXE_SUFFIX}"

# ---------------------------------------------------------------------------
# Step 1 — preflight
# ---------------------------------------------------------------------------

echo "── [1/6] preflight: verify SDK + cmdline-tools"
if [[ ! -x "$AVDMANAGER" ]] && [[ ! -f "$AVDMANAGER" ]]; then
    cat <<EOF >&2

ERROR: avdmanager not found at:
       $AVDMANAGER

The Android SDK Command-line Tools haven't been installed yet.
Install them via one of:

  A. Android Studio → Settings → Languages & Frameworks →
     Android SDK → SDK Tools tab → check "Android SDK Command-line
     Tools (latest)" → Apply.

  B. Manual download from https://developer.android.com/studio
     → "Command line tools only" → Windows zip → unzip
     cmdline-tools/ → rename to "latest" → place under
     $SDK_ROOT/cmdline-tools/

Then re-run this script.
EOF
    exit 3
fi

if [[ ! -f "$EMULATOR" ]]; then
    echo "ERROR: emulator binary not found at $EMULATOR" >&2
    echo "Install via Android Studio SDK Manager → SDK Tools → Android Emulator." >&2
    exit 3
fi

if [[ ! -f "$ADB" ]]; then
    echo "ERROR: adb not found at $ADB" >&2
    exit 3
fi

# ---------------------------------------------------------------------------
# Step 2 — create AVD if none exists
# ---------------------------------------------------------------------------

echo "── [2/6] AVD: create '$AVD_NAME' if absent"
existing_avds=$("$AVDMANAGER" list avd -c 2>/dev/null || true)
if echo "$existing_avds" | grep -qx "$AVD_NAME"; then
    echo "    reusing existing AVD '$AVD_NAME'"
else
    if [[ ! -d "$SDK_ROOT/${SYSTEM_IMAGE//;//}" ]]; then
        echo "    system image $SYSTEM_IMAGE not present; downloading..."
        yes | "$SDKMANAGER" --install "$SYSTEM_IMAGE" >/dev/null
    fi
    echo "    creating AVD '$AVD_NAME' (image=$SYSTEM_IMAGE, device=$DEVICE_PROFILE)"
    echo "no" | "$AVDMANAGER" create avd \
        --name "$AVD_NAME" \
        --package "$SYSTEM_IMAGE" \
        --device "$DEVICE_PROFILE" \
        --force >/dev/null
fi

# ---------------------------------------------------------------------------
# Step 3 — boot emulator headless
# ---------------------------------------------------------------------------

echo "── [3/6] boot emulator headless"
"$EMULATOR" -avd "$AVD_NAME" \
    -no-window -no-audio -no-snapshot -no-boot-anim \
    -gpu swiftshader_indirect \
    >/tmp/emulator-$$.log 2>&1 &
EMULATOR_PID=$!

cleanup() {
    if [[ "$KEEP_RUNNING" -eq 1 ]]; then
        echo "── --keep-running set; emulator left running (PID $EMULATOR_PID)"
        return
    fi
    if kill -0 "$EMULATOR_PID" 2>/dev/null; then
        echo "── teardown: stopping emulator (PID $EMULATOR_PID)"
        "$ADB" emu kill 2>/dev/null || kill "$EMULATOR_PID" 2>/dev/null || true
        wait "$EMULATOR_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 4 — wait for boot
# ---------------------------------------------------------------------------

echo "── [4/6] wait for boot (timeout=${BOOT_TIMEOUT_SECONDS}s)"
"$ADB" wait-for-device

deadline=$(( $(date +%s) + BOOT_TIMEOUT_SECONDS ))
while true; do
    if [[ "$(date +%s)" -gt "$deadline" ]]; then
        echo "ERROR: emulator did not finish booting within ${BOOT_TIMEOUT_SECONDS}s" >&2
        echo "    last 30 lines of emulator log:" >&2
        tail -30 "/tmp/emulator-$$.log" >&2 || true
        exit 4
    fi
    booted=$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    if [[ "$booted" == "1" ]]; then
        echo "    boot complete"
        break
    fi
    sleep 2
done

# Slight settle delay — package manager / IME services finish coming up
# slightly after boot_completed flips.
sleep 5

# ---------------------------------------------------------------------------
# Step 5 — run instrumented tests
# ---------------------------------------------------------------------------

echo "── [5/6] ./gradlew :app:connectedAndroidTest"
cd "$(dirname "$0")/../android"
./gradlew :app:connectedAndroidTest

# ---------------------------------------------------------------------------
# Step 6 — done; trap handles teardown
# ---------------------------------------------------------------------------

echo "── [6/6] all instrumented tests green"
