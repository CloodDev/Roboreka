# Roboreka

Lightweight Python VoIP (SIP + RTP + DTMF) server tailored for the **FriendlyElec NanoPi NEO v1.4** (Allwinner H3) that turns a robot arm over I2C using a **PCA9685** 16-channel PWM servo controller.

Zero compiled external runtime dependencies — runs smoothly within the NanoPi NEO's 256/512 MB RAM and ARMv7 CPU, and includes a register-accurate mock I2C bus (`--mock`) for development and testing on Windows/macOS/Linux without hardware attached.

---

## Architecture

```
SIP Softphone / roboreka-call
   │
   ├─ SIP/UDP (:5060)  ── INVITE / ACK / INFO / BYE ──▶ SIPServer
   │                                                        │
   └─ RTP/UDP (:10000+) ─ PCMU Audio & RFC 4733 Events ─▶ RTPSession
                            │                               │
                            ▼                               ▼
                    HybridDTMFDetector               G.711 PCMU Feedback
                 (RFC 4733 + Goertzel + INFO)       (Chimes / Ack Beeps / Buzz)
                            │
                            ▼
                        RobotArm (smooth 50 Hz ramps & angle limits)
                            │
                            ▼
                     PCA9685 Driver (0x40)
                            │
                            ▼
               NanoPi NEO v1.4 I2C0 (/dev/i2c-0)
                  (or MockI2CBus in dev/test)
```

---

## NanoPi NEO v1.4 Hardware Wiring

On the **NanoPi NEO v1.4**, the 24-pin `GPIO1` header exposes **I2C0 (`/dev/i2c-0`)** on physical pins 3 & 5:

| NanoPi NEO v1.4 `GPIO1` Pin | Signal | SoC Ball | PCA9685 Pin |
| :--- | :--- | :--- | :--- |
| **Pin 1** | `3.3V` | — | `VCC` (logic power) |
| **Pin 3** | `I2C0_SDA` | `PA12` | `SDA` |
| **Pin 5** | `I2C0_SCL` | `PA11` | `SCL` |
| **Pin 6** | `GND` | — | `GND` |

> **Important:** Power the PCA9685 **servo power rail (`V+`)** from a dedicated external **5V–6V** DC supply sized for your servos, with its ground connected to common `GND`. Never power robot arm servos from the NanoPi NEO's 3.3V or USB 5V rail.

---

## Enabling I2C0 on NanoPi NEO v1.4 (Armbian / FriendlyCore)

1. Enable the `i2c0` Device Tree overlay:
   - Interactive: run `sudo armbian-config` → **System** → **Hardware** → select **`i2c0`** → Save & reboot.
   - Manual: edit `/boot/armbianEnv.txt` and ensure `i2c0` is listed:
     ```ini
     overlays=i2c0
     ```
     Then reboot (`sudo reboot`).
2. Verify `/dev/i2c-0` exists and detects the PCA9685 (`0x40`):
   ```bash
   sudo apt update && sudo apt install -y i2c-tools
   sudo i2cdetect -y 0
   ```
   You should see `40` in the I2C address table.
3. Grant your user permission to access `/dev/i2c-0` without root:
   ```bash
   sudo usermod -aG i2c "$USER"
   # Log out and back in for group membership to take effect
   ```

---

## Installation

### On NanoPi NEO v1.4 (with hardware I2C)

`smbus2` is pure Python, so no C compiler toolchain is required on ARMv7:

```bash
git clone <your-repo-url> Roboreka
cd Roboreka
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[hardware]"
```

*(Alternatively, system package `python3-smbus` is also supported automatically.)*

### On a Dev Machine (Windows / macOS / Linux without I2C hardware)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Usage

### 1. Start the VoIP-to-I2C Server

On NanoPi NEO v1.4 (uses `/dev/i2c-0` at `0x40` by default):

```bash
cp config.example.toml config.toml
roboreka-server --config config.toml
```

On a dev machine without I2C hardware (uses in-memory `MockI2CBus`):

```bash
roboreka-server --mock --host 127.0.0.1 --sip-port 15060
```

### 2. Dial with the Built-in Softphone Client (`roboreka-call`)

Send a scripted DTMF sequence (RFC 4733 by default):

```bash
roboreka-call 127.0.0.1:15060 --digits "66425"
```

Test in-band Goertzel audio DTMF or SIP `INFO` relay:

```bash
roboreka-call 127.0.0.1:15060 --mode inband --digits "645"
roboreka-call 127.0.0.1:15060 --mode info --digits "315"
```

Or omit `--digits` for interactive keypad entry from stdin.

### 3. Connect Any Standard SIP Softphone

Configure Linphone, MicroSIP, or Zoiper to dial `sip:arm@<nanopi-ip>:5060` directly over UDP (no SIP registrar required; select **PCMU / G.711 µ-law** and RFC 4733 or in-band DTMF).

---

## DTMF Keypad Mapping

| Key | Action | Default Joint / Channel |
| :---: | :--- | :--- |
| **`4`** / **`6`** | Turn base left / right (`-step` / `+step`) | `base` (ch 0) |
| **`1`** / **`3`** | Turn base fast left / right (`-3*step` / `+3*step`) | `base` (ch 0) |
| **`2`** / **`8`** | Shoulder up / down | `shoulder` (ch 1) |
| **`7`** / **`9`** | Elbow down / up | `elbow` (ch 2) |
| **`*`** / **`#`** | Gripper close / open | `gripper` (ch 3) |
| **`5`** | Home all joints smoothly | All joints |
| **`0`** | Emergency stop & release PWM on all servos | All channels off |

Audio feedback cues streamed back to the caller over RTP:
- **Call connected:** Rising 3-note welcome chime
- **Joint moved:** Short pitch-mapped acknowledgment beep (higher pitch = higher angle)
- **Limit reached:** Low double-tone warning buzz
- **Home (`5`):** Ascending 3-note home chime
- **Stop (`0`):** Descending alert tone

---

## Running as a systemd Service on NanoPi NEO v1.4

A ready-to-use service unit is included at `deploy/roboreka.service`:

```bash
sudo mkdir -p /etc/roboreka
sudo cp config.example.toml /etc/roboreka/config.toml
sudo cp deploy/roboreka.service /etc/systemd/system/roboreka.service
sudo systemctl daemon-reload
sudo systemctl enable --now roboreka
sudo journalctl -u roboreka -f
```

---

## Running Tests

```bash
pytest -v
```
