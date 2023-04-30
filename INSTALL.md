```bash
sudo apt install build-essential
sudo apt-get install python3-distutils
sudo apt-get install python3-apt
sudo apt update
sudo apt upgrade

sudo iwconfig wlan0 power off

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install --git https://github.com/mitsuhiko/rye rye
```

```bash
rye sync

# macOS
# Hack macos
cd .venv/lib/python3.11/site-packages
git clone git@github.com:pimoroni/inky.git
replace whole inky folder with library/inky
WI_DIR="~/Documents/personal/code/rasp/inky/weather-impression" DEBUG=true rye run python3 weather.py

# linux
rye add inky
rye sync

DEBUG=true python3 weather.py

# WI_DIR="/home/pi/inky/weather-impression"
WI_DIR="~/Documents/personal/code/rasp/inky/weather-impression"
```