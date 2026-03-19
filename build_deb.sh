#!/bin/bash
set -e

APP_NAME="morse-converter"
# Extract version from morse_logic.py
VERSION=$(grep "VERSION =" morse_logic.py | cut -d'"' -f2)
PKG_DIR="package_root"

echo "Building Debian package for $APP_NAME v$VERSION..."

# 1. Create directory structure
rm -rf $PKG_DIR
mkdir -p $PKG_DIR/DEBIAN
mkdir -p $PKG_DIR/usr/bin
mkdir -p $PKG_DIR/usr/share/$APP_NAME
mkdir -p $PKG_DIR/usr/share/applications

# 2. Create control file
cat << EOF > $PKG_DIR/DEBIAN/control
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-tk, nodejs, npm, espeak
Maintainer: Gemini CLI <gemini-cli@example.com>
Description: Morse Code to MP3 Converter
 A graphical utility to convert text to Morse code MP3 files 
 with support for Farnsworth timing and random practice groups.
EOF

# 3. Create desktop entry
cat << EOF > $PKG_DIR/usr/share/applications/$APP_NAME.desktop
[Desktop Entry]
Name=Morse Converter
Comment=Convert text to Morse code MP3
Exec=$APP_NAME
Icon=audio-x-generic
Terminal=false
Type=Application
Categories=Education;Utility;
EOF

# 4. Create executable wrapper
cat << EOF > $PKG_DIR/usr/bin/$APP_NAME
#!/bin/bash
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "Error: tkinter (python3-tk) is not installed."
    echo "Attempting to fix dependencies..."
    sudo apt-get update && sudo apt-get install -y python3-tk
fi
cd /usr/share/$APP_NAME
python3 morse_gui.py "\$@"
EOF
chmod +x $PKG_DIR/usr/bin/$APP_NAME

# 5. Copy application files
cp morse_logic.py $PKG_DIR/usr/share/$APP_NAME/
cp morse_gui.py $PKG_DIR/usr/share/$APP_NAME/

# 6. Install node-lame dependency locally in the package
echo "Installing node-lame dependency inside package..."
cd $PKG_DIR/usr/share/$APP_NAME
npm install node-lame --silent
cd -

# 7. Build the package
dpkg-deb --build --root-owner-group $PKG_DIR "${APP_NAME}_${VERSION}_all.deb"

echo "Done! Package created: ${APP_NAME}_${VERSION}_all.deb"
