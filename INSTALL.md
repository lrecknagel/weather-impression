## Prepare system

```bash
sudo apt install build-essential
sudo apt-get install python3-distutils
sudo apt-get install python3-apt
sudo apt update
sudo apt upgrade

# optional
sudo iwconfig wlan0 power off

# needed currently by rye to be installed successfully
sudo apt install libssl-dev

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install --git https://github.com/mitsuhiko/rye rye
```

## Debugging

```bash
rye sync

# macOS (hacky because inky lib requires spidev hard which does not work in macOS)
cd .venv/lib/python3.11/site-packages
git clone git@github.com:pimoroni/inky.git
replace whole inky folder with library/inky
WI_DIR="<PATH_WEATHER_IMPRESSION_FOLDER>/weather-impression" DEBUG=true rye run python3 weather.py

# linux
rye add inky
rye sync

WI_DIR="<PATH_WEATHER_IMPRESSION_FOLDER>/weather-impression" DEBUG=true rye run python3 weather.py
```

TODO: fix setup with: pip3 install inky[rpi,example-depends]
TODO: https://github.com/mitsuhiko/rye/issues/77
TODO:
  sudo raspi-config
  -> Interfacing Options
  -> SPI enable

## Permanent systemd setup

```bash
# Setup cron

sudo vim /etc/systemd/system/weatherimpression.service


[Unit]
Description=Weather Impression Service for Inky
After=multi-user.target
[Service]
Type=simple
Restart=always
Environment=WI_DIR=<PATH_WEATHER_IMPRESSION_FOLDER>/weather-impression
WorkingDirectory=/home/pi/
User=pi
ExecStart=/usr/bin/python3 <PATH_WEATHER_IMPRESSION_FOLDER>/weather-impression/watcher.py
[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl enable weatherimpression.service
sudo systemctl start weatherimpression.service
sudo journalctl -f -u weatherimpression.service
```