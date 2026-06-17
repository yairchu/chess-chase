#!/bin/sh
set -eu

version=$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
app="dist/Chess Chase.app"
zip="chesschase-mac-v$version.zip"
notary_json="/tmp/chesschase-notary-$version.json"
default_identity=$(security find-identity -v -p codesigning | awk -F\" '/Developer ID Application: Yair Chuchem / { print $2; exit }')

: "${CODESIGN_IDENTITY:=$default_identity}"
: "${CODESIGN_IDENTITY:?Set CODESIGN_IDENTITY to your Developer ID Application identity}"
: "${NOTARY_PROFILE:?Set NOTARY_PROFILE to your notarytool keychain profile}"
export CODESIGN_IDENTITY

uv sync --extra macos-build
uv run python generate_icons.py
PYINSTALLER_VERIFY_BUNDLE_SIGNATURE=1 uv run pyinstaller --clean --noconfirm "Chess Chase.spec"

codesign --verify --deep --strict --verbose=2 "$app"

rm -f "$zip"
ditto -c -k --norsrc --keepParent "$app" "$zip"
zip_check_dir=$(mktemp -d)
/usr/bin/unzip -q "$zip" -d "$zip_check_dir"
codesign --verify --deep --strict --verbose=2 "$zip_check_dir/Chess Chase.app"

xcrun notarytool submit "$zip" \
    --keychain-profile "$NOTARY_PROFILE" \
    --wait \
    --output-format json > "$notary_json"
notary_id=$(uv run python -c 'import json, sys; data=json.load(open(sys.argv[1])); print(data["id"])' "$notary_json")
notary_status=$(uv run python -c 'import json, sys; data=json.load(open(sys.argv[1])); print(data["status"])' "$notary_json")
echo "notary: $notary_status ($notary_id)"
if [ "$notary_status" != Accepted ]; then
    xcrun notarytool log "$notary_id" --keychain-profile "$NOTARY_PROFILE"
    exit 1
fi

xcrun stapler staple "$app"
codesign --verify --deep --strict --verbose=2 "$app"
xcrun stapler validate "$app"
rm -f "$zip"
ditto -c -k --norsrc --keepParent "$app" "$zip"
zip_check_dir=$(mktemp -d)
/usr/bin/unzip -q "$zip" -d "$zip_check_dir"
codesign --verify --deep --strict --verbose=2 "$zip_check_dir/Chess Chase.app"

echo "$zip"
