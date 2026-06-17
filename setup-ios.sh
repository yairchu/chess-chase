#!/bin/sh
set -eu

app_name=ChessChase
app_dir=${IOS_APP_DIR:-build/ios/app}
project_dir=$app_name-ios

xcode-select -p >/dev/null
if ! xcodebuild -showComponent MetalToolchain >/dev/null 2>&1; then
    echo "Missing Xcode Metal toolchain. Run: xcodebuild -downloadComponent MetalToolchain" >&2
    exit 1
fi
uv sync

rm -rf "$app_dir"
mkdir -p "$app_dir"
cp main.py board_view.py chess.py chess.png env.py game_model.py net_engine.py ssl_certs.py widgets.py "$app_dir"
stun_dir=$(uv run python -c 'import pathlib, stun; print(pathlib.Path(stun.__file__).parent)')
cp -R "$stun_dir" "$app_dir/stun"
certifi_dir=$(uv run python -c 'import certifi, pathlib; print(pathlib.Path(certifi.__file__).parent)')
cp -R "$certifi_dir" "$app_dir/certifi"

if [ "${IOS_PREPARE_ONLY:-}" = 1 ]; then
    echo "$app_dir"
    exit 0
fi

uv tool run --from kivy-ios toolchain build python3 kivy

app_dir_abs=$(cd "$app_dir" && pwd)
if [ -d "$project_dir" ]; then
    uv tool run --from kivy-ios toolchain update "$project_dir"
else
    uv tool run --from kivy-ios toolchain create "$app_name" "$app_dir_abs"
fi

plist=$(find "$project_dir" -name '*-Info.plist' -print -quit)
/usr/libexec/PlistBuddy -c 'Set :UIRequiresFullScreen true' "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c 'Add :UIRequiresFullScreen bool true' "$plist"
/usr/libexec/PlistBuddy -c "Set :NSCameraUsageDescription Kivy includes a camera provider, but Chess Chase does not use the camera." "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string Kivy includes a camera provider, but Chess Chase does not use the camera." "$plist"
/usr/libexec/PlistBuddy -c "Set :NSLocalNetworkUsageDescription Chess Chase uses direct peer-to-peer networking for multiplayer games." "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSLocalNetworkUsageDescription string Chess Chase uses direct peer-to-peer networking for multiplayer games." "$plist"
open "$project_dir/$app_name.xcodeproj"
