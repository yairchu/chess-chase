#!/bin/sh
set -eu

app_name=ChessChase
project_name=chesschase
bundle_id=org.kivy.chess-chase
icon_source="Chess Chase.png"
version=$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
build_number=${IOS_BUILD_NUMBER:-$(date +%Y%m%d%H%M)}
app_dir=${IOS_APP_DIR:-build/ios/app}
project_dir=$project_name-ios

write_ios_icons() {
    iconset="$project_dir/$project_name/Images.xcassets/AppIcon.appiconset"
    mkdir -p "$iconset"
    tmp_icon="$iconset/source-icon.png"
    cp "$icon_source" "$tmp_icon"
    for size in 20 29 40 58 60 76 80 87 120 152 167 180 1024; do
        sips --resampleHeightWidth "$size" "$size" "$tmp_icon" --out "$iconset/AppIcon-$size.png" >/dev/null
    done
    rm -f "$tmp_icon"
    python3 - "$iconset/Contents.json" <<'PY'
import json
import sys

images = [
    ("iphone", "20x20", "2x", "AppIcon-40.png"),
    ("iphone", "20x20", "3x", "AppIcon-60.png"),
    ("iphone", "29x29", "2x", "AppIcon-58.png"),
    ("iphone", "29x29", "3x", "AppIcon-87.png"),
    ("iphone", "40x40", "2x", "AppIcon-80.png"),
    ("iphone", "40x40", "3x", "AppIcon-120.png"),
    ("iphone", "60x60", "2x", "AppIcon-120.png"),
    ("iphone", "60x60", "3x", "AppIcon-180.png"),
    ("ipad", "20x20", "2x", "AppIcon-40.png"),
    ("ipad", "20x20", "1x", "AppIcon-20.png"),
    ("ipad", "29x29", "1x", "AppIcon-29.png"),
    ("ipad", "29x29", "2x", "AppIcon-58.png"),
    ("ipad", "40x40", "1x", "AppIcon-40.png"),
    ("ipad", "40x40", "2x", "AppIcon-80.png"),
    ("ipad", "76x76", "1x", "AppIcon-76.png"),
    ("ipad", "76x76", "2x", "AppIcon-152.png"),
    ("ipad", "83.5x83.5", "2x", "AppIcon-167.png"),
    ("ios-marketing", "1024x1024", "1x", "AppIcon-1024.png"),
]
contents = {
    "images": [
        {"idiom": idiom, "size": size, "scale": scale, "filename": filename}
        for idiom, size, scale, filename in images
    ],
    "info": {"version": 1, "author": "xcode"},
}
with open(sys.argv[1], "w") as f:
    json.dump(contents, f, indent=2)
    f.write("\n")
PY
}

xcode-select -p >/dev/null
if [ "${IOS_SKIP_METAL_CHECK:-}" != 1 ] && ! xcodebuild -showComponent MetalToolchain >/dev/null 2>&1; then
    echo "Missing Xcode Metal toolchain. Run: xcodebuild -downloadComponent MetalToolchain" >&2
    exit 1
fi
uv sync

rm -rf "$app_dir"
mkdir -p "$app_dir"
cp main.py board_view.py chess.py chess-chase-pieces.png background.jpg logo.png env.py game_model.py net_engine.py ssl_certs.py widgets.py "$app_dir"
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
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $bundle_id" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $version" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $build_number" "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIconName AppIcon' "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c 'Add :CFBundleIconName string AppIcon' "$plist"
/usr/libexec/PlistBuddy -c 'Set :UIRequiresFullScreen true' "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c 'Add :UIRequiresFullScreen bool true' "$plist"
/usr/libexec/PlistBuddy -c 'Set :ITSAppUsesNonExemptEncryption false' "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c 'Add :ITSAppUsesNonExemptEncryption bool false' "$plist"
/usr/libexec/PlistBuddy -c "Set :NSCameraUsageDescription Kivy includes a camera provider, but Chess Chase does not use the camera." "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string Kivy includes a camera provider, but Chess Chase does not use the camera." "$plist"
/usr/libexec/PlistBuddy -c "Set :NSLocalNetworkUsageDescription Chess Chase uses direct peer-to-peer networking for multiplayer games." "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSLocalNetworkUsageDescription string Chess Chase uses direct peer-to-peer networking for multiplayer games." "$plist"
write_ios_icons
open "$project_dir/$project_name.xcodeproj"
