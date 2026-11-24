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

First enable the board's I2C0 overlay as described above and reboot. From a
Roboreka checkout, run the installer on Armbian:

```bash
sudo bash ./install.sh
```

The installer installs the application under `/opt/roboreka`, creates separate
service accounts and systemd units for the arm controller and web UI, and
enables both services. It creates
`/etc/roboreka/config.toml` from the example only when the file does not already
exist, so rerunning the installer preserves your configuration. If `/dev/i2c-0`
is not available yet, the service is enabled but not started; enable I2C, reboot,
and then run `sudo systemctl start roboreka roboreka-web`.

`smbus2` is pure Python, so no C compiler toolchain is required on ARMv7.
*(Alternatively, system package `python3-smbus` is also supported automatically.)*

### Assigning PCA9685 servo channels

Set `channel` separately in each `[[arm.joints]]` block in
`/etc/roboreka/config.toml`. Use a channel from `0` to `15`, and assign a
different channel to each servo. For example, to move the base servo from
channel 0 to channel 7:

```toml
[[arm.joints]]
name = "base"
channel = 7
```

You can edit these values in the dashboard's configuration editor or directly
in the TOML file. Restart the service after saving:
`sudo systemctl restart roboreka`.

Roboreka runs as two separate applications:

- **Arm controller** (`roboreka-server`) owns the I2C hardware and SIP server,
  and exposes a loopback-only control API on port `8081`.
- **Web UI** (`roboreka-web`) serves the browser interface on port `8080` and
  forwards UI requests to the controller API.

On Armbian, the installer enables these as separate `roboreka` and
`roboreka-web` systemd services. The web UI provides live arm controls, logs,
status, the action-block editor, and config editing. Config changes are
validated and saved but require restarting the arm controller to apply:
`sudo systemctl restart roboreka`. Both apps listen on loopback by default; to
access the UI remotely, forward the web port over SSH:

```bash
ssh -L 8080:127.0.0.1:8080 <user>@<nanopi-ip>
```

Then open `http://127.0.0.1:8080` on your computer. For manual startup, run
`roboreka-server --config /etc/roboreka/config.toml` and, in a second terminal,
`roboreka-web --api-url http://127.0.0.1:8081`. The web UI can be disabled or
stopped independently without stopping SIP calls or arm control. Use
`roboreka-server --no-api` to disable the local control API. The service account
must have write permission to `/etc/roboreka` for config editing; otherwise the
editor is read-only.

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

In a second terminal, start its separate web UI:

```bash
roboreka-web --api-url http://127.0.0.1:8081
```

Open `http://127.0.0.1:8080` to view and control the mock arm.

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

### Automatic action when a call connects

You can configure an automatic sequence of arm poses in the `[arm]` section of
`config.toml`. When a call is answered, the server moves smoothly to each pose
in order, waits for its optional `hold_s`, then returns **all joints** to their
configured `home_angle`. During this automatic movement, keypad commands are
ignored. After the arm returns home, the normal DTMF controls remain available
for the rest of the call.

For example, add these entries before the `[[arm.joints]]` blocks. Adjust the
angles to suit your arm's safe range:

```toml
[[arm.call_sequence]]
angles = { base = 105.0, shoulder = 90.0 }
hold_s = 0.5

[[arm.call_sequence]]
angles = { base = 90.0, shoulder = 105.0 }
hold_s = 0.5
```

Each pose can specify any subset of joints; unspecified joints hold their
position. Angles outside a joint's configured limits, unknown joints, and
negative hold times are rejected. The sequence runs only when at least one
`[[arm.call_sequence]]` entry is configured. Save the config and restart
Roboreka to apply it.

You can also build and reorder pose blocks with the dashboard's **Call action
blocks** editor. Adjust each joint's rotation, set the wait time for each pose,
and choose **Save call action**; the TOML editor updates with the saved sequence.

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
sudo cp deploy/roboreka-web.service /etc/systemd/system/roboreka-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now roboreka roboreka-web
sudo journalctl -u roboreka -f
```

---

## Running Tests

```bash
pytest -v
```
