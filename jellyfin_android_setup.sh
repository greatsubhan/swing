ww ute #!/bin/bash
# ============================================================
# Jellyfin Media Server Setup for Termux on Android
# Run this script INSIDE Termux on your Android phone
# ============================================================
# Usage: Copy this to your phone, then in Termux run:
#   chmod +x jellyfin_android_setup.sh
#   ./jellyfin_android_setup.sh
# ============================================================

set -e

echo "==================================="
echo " Jellyfin Setup for Termux + Ubuntu"
echo "==================================="
echo ""

# --- Step 1: Update Termux packages ---
echo "[1/8] Updating Termux packages..."
pkg update -y && pkg upgrade -y
pkg install -y proot-distro curl wget

# --- Step 2: Install Ubuntu via proot-distro ---
echo "[2/8] Installing Ubuntu via proot-distro..."
if proot-distro list | grep -q "ubuntu"; then
    echo "Ubuntu is already installed, skipping..."
else
    proot-distro install ubuntu
fi

# --- Step 3: Write the Jellyfin install script for inside Ubuntu ---
echo "[3/8] Creating Jellyfin install script for Ubuntu..."

cat > ~/install_jellyfin_inside_ubuntu.sh << 'UBUNTU_SCRIPT'
#!/bin/bash
# Run this INSIDE Ubuntu: proot-distro login ubuntu

echo "=== Installing Jellyfin inside Ubuntu ==="

# Update Ubuntu
apt update -y && apt upgrade -y

# Install prerequisites
apt install -y curl gnupg apt-transport-https ca-certificates software-properties-common

# Add Jellyfin repository
curl -fsSL https://repo.jellyfin.org/jellyfin_team.gpg.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/jellyfin.gpg

# Detect architecture
ARCH=$(dpkg --print-architecture)
echo "Architecture: $ARCH"

# Add the repo based on architecture
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "deb [arch=arm64] https://repo.jellyfin.org/ubuntu jammy main" > /etc/apt/sources.list.d/jellyfin.list
elif [ "$ARCH" = "armhf" ] || [ "$ARCH" = "armv7l" ]; then
    echo "deb [arch=armhf] https://repo.jellyfin.org/ubuntu jammy main" > /etc/apt/sources.list.d/jellyfin.list
else
    echo "deb [arch=amd64] https://repo.jellyfin.org/ubuntu jammy main" > /etc/apt/sources.list.d/jellyfin.list
fi

# Install Jellyfin
apt update -y
apt install -y jellyfin

# Create start script for Jellyfin
cat > /opt/jellyfin_start.sh << 'START_SCRIPT'
#!/bin/bash
# Start Jellyfin server
export JELLYFIN_DATA_DIR="/var/lib/jellyfin"
export JELLYFIN_CONFIG_DIR="/etc/jellyfin"
export JELLYFIN_CACHE_DIR="/var/cache/jellyfin"
export JELLYFIN_LOG_DIR="/var/log/jellyfin"

mkdir -p $JELLYFIN_DATA_DIR $JELLYFIN_CONFIG_DIR $JELLYFIN_CACHE_DIR $JELLYFIN_LOG_DIR

# Start jellyfin in background
/usr/bin/jellyfin \
    --datadir "$JELLYFIN_DATA_DIR" \
    --configdir "$JELLYFIN_CONFIG_DIR" \
    --cachedir "$JELLYFIN_CACHE_DIR" \
    --logdir "$JELLYFIN_LOG_DIR" \
    --port 8080 &
    
echo "Jellyfin started on port 8080"
START_SCRIPT

chmod +x /opt/jellyfin_start.sh

# Create a symlink for media storage
echo ""
echo "IMPORTANT: After setup, link your media folders:"
echo "  ln -s /storage/emulated/0/Movies /media/movies"
echo "  ln -s /storage/emulated/0/TV Shows /media/tvshows"
echo "  ln -s /storage/emulated/0/Music /media/music"

echo "=== Jellyfin installation complete! ==="
echo "To start Jellyfin, run: /opt/jellyfin_start.sh"
echo "Access it at: http://localhost:8080"
echo "For other devices on your network: http://YOUR_PHONE_IP:8080"
UBUNTU_SCRIPT

chmod +x ~/install_jellyfin_inside_ubuntu.sh

# --- Step 4: Media folder setup ---
echo "[4/8] Setting up media folders..."
mkdir -p ~/media/movies ~/media/tvshows ~/media/music

echo ""
echo "=== Setup Guide ==="
echo "================================================================"
echo ""
echo "PART 1: Install Jellyfin (run in Termux):"
echo "  proot-distro login ubuntu"
echo "  cd /root && bash /root/install_jellyfin_inside_ubuntu.sh"
echo "  /opt/jellyfin_start.sh"
echo "  exit"
echo ""
echo "PART 2: Link your phone's storage to Ubuntu (run in Termux):"
echo "  proot-distro login ubuntu"
echo "  mkdir -p /media/movies /media/tvshows /media/music"
echo "  # The phone's internal storage is at /sdcard in Termux"
echo "  # But inside proot, it's at /storage/emulated/0"
echo "  exit"
echo "  # Outside: copy media to ~/media/"
echo "  cp -r /sdcard/Movies ~/media/"
echo "  cp -r /sdcard/Music ~/media/"
echo "  # OR: use a bind mount approach"
echo ""
echo "PART 3: Auto-start on boot:"
echo "  pkg install termux-services"
echo "  # Then create ~/.termux/boot/start_jellyfin.sh"
echo ""
echo "PART 4: Access Jellyfin:"
echo "  On the phone browser: http://localhost:8080"
echo "  From PC/smart TV:      http://192.168.1.119:8080"
echo "  Jellyfin runs on port 8080"
echo ""
echo "================================================================"
echo ""

# --- Check what's on port 8080 ---
echo "Checking what's currently on port 8080..."
if command -v netstat &> /dev/null; then
    netstat -tlnp 2>/dev/null | grep 8080 || echo "Nothing found with netstat"
fi
if [ -f /proc/net/tcp ]; then
    echo "Port 8080 is already in use (something is running there)"
    echo "Jellyfin will kill that process and reuse port 8080"
fi

echo ""
echo "Done! Follow the instructions above."
echo "Next step: proot-distro login ubuntu"