# Genesis Mini — Agentic Operating System (AOS) v0.2.0

On-device firmware for the **Axiometa Genesis Mini** (ESP32-S3-Mini-1-N4R2).
This tree lives under the Agentic OS monorepo (`firmware/genesis-mini/`) alongside
EverOS memory and the (future) bridge/sync layer.

Phase 0 scope: boot, SD agent manifest, AX22 module slots, serial REPL, optional
LLM chat completions. Bridge/sync is intentionally **not** included yet (Phase 3).

## Hardware

| Item | Detail |
|------|--------|
| MCU | ESP32-S3-Mini-1-N4R2 |
| Flash / PSRAM | 4 MB / 2 MB |
| Status LED | NeoPixel on GPIO 21 |
| Button | GPIO 45 (active low) |
| I2C | SDA 10, SCL 11 (OLED optional) |
| SPI | MOSI 12, MISO 13, SCK 14 |
| Port 1 | microSD (CS GPIO 15) |
| Ports 2–4 | AX22 GPIO triples — see `include/board_pins.h` |

PlatformIO board target: `esp32-s3-devkitc-1` (compatible pinout / S3 Arduino core).

## Build / flash / monitor

From this directory:

```bash
cd firmware/genesis-mini
pio run
pio run -t upload
pio device monitor -b 115200
```

Or one shot:

```bash
pio run -t upload -t monitor
```

Requires [PlatformIO Core](https://platformio.org/) and a USB connection to the
Genesis Mini (CDC on boot is enabled).

## SD card

Copy the image under `sdcard/AOS/` to the card root as `/AOS/…`, or use:

```bash
python tools/prepare_sd.py /path/to/card \
  --wifi-ssid "MyNet" --wifi-pass "secret" \
  --llm-enabled true --llm-api-key "sk-..."
```

Swap a port profile:

```bash
python tools/apply_profile.py /path/to/card/AOS 4 control --label "Relay"
```

### Layout

```
AOS/
  AGENT/manifest.json      # name, wifi, llm
  AGENT/personality.txt
  AGENT/memory.jsonl       # created at runtime by remember()
  MODULES/port{2,3,4}.json
  MODULES/profiles/*.json
  MODULES/catalog.json
  INSTALL/                 # Phase 3 packages
  LOGS/
```

## Serial commands

| Command | Action |
|---------|--------|
| `help` | Show command list |
| `status` | System + agent status |
| `modules` | List AX22 slots |
| `read N` | Read module on port N (2–4) |
| `write N …` | Write payload (`on`/`off`/`toggle`/JSON) |
| `beep N` | Buzz on port N pin b |
| `ask <q>` | Local tools first, optional LLM |
| `install` | Phase 0 stub for `/AOS/INSTALL` |

Banner and `status` print `AOS_VERSION` from the build flag (`0.2.0`), not a
hardcoded older string.

## Project layout

```
firmware/genesis-mini/
  platformio.ini
  include/          # board + module headers
  src/              # firmware sources
  sdcard/AOS/       # reference SD image
  tools/            # prepare_sd.py, apply_profile.py
  README.md
```
