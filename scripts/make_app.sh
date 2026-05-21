#!/bin/bash
# Build Winter.app — a thin alias-style bundle. The launcher runs the LIVE
# source via the project .venv, so editing code and relaunching picks up
# changes with no rebuild. Not portable to other Macs (paths are absolute).
#
# Re-run this if the project moves:  bash scripts/make_app.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$PROJECT_ROOT/Winter.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Winter</string>
  <key>CFBundleDisplayName</key><string>Winter</string>
  <key>CFBundleIdentifier</key><string>com.winter.assistant</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleExecutable</key><string>winter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>Winter listens for your wake word and voice commands.</string>
  <key>NSCameraUsageDescription</key><string>Winter watches the camera for hand gestures.</string>
</dict>
</plist>
PLIST

# launcher — $PROJECT_ROOT is expanded now so the path is baked in
cat > "$APP/Contents/MacOS/winter" <<LAUNCH
#!/bin/bash
cd "$PROJECT_ROOT"
exec "$PROJECT_ROOT/.venv/bin/python" -m winter >> /tmp/winter.log 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/winter"

echo "Built $APP"
