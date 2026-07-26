# FPGA Tactile Sensor Array
A capacitive tactile sensor array with FPGA-based sensing.
<img width="1148" height="616" alt="image" src="https://github.com/user-attachments/assets/6fac019d-0a08-428a-be55-ee74707bc94b" />

---

# 🔧 Part 1: iCE40HX8K Setup Guide

This section covers everything needed to build and run the tactile sensor system on the **Lattice iCE40-HX8K Breakout Board**.

## 1. What You Need (Bill of Materials)

| Item | Qty | Description | Link / Source |
|------|-----|-------------|---------------|
| **iCE40HX8K Breakout** | 1 | Lattice iCE40-HX8K CT256 Breakout Board | Lattice Semiconductor |
| **Main Shield PCB** | 1 | Custom 4-layer PCB (see `PCB_ICE40HX8K/`) | Fabricate from gerbers |
| **FPC Connector** | 2 | 50-pin, 0.5 mm pitch, bottom contact | [Würth 687150149022 (DigiKey)](https://www.digikey.jp/ja/products/detail/w%C3%BCrth-elektronik/687150149022/5047807) |
| **Resistors** | 100 | 0402 SMD, 10 MΩ | [YAGEO RC0402JR-1010ML (Mouser)](https://www.mouser.jp/ja/ProductDetail/YAGEO/RC0402JR-1010ML?qs=qpJ%252B%252B%252Bdg6p0Cmvh%2FWhcluQ%3D%3D) |
| **FPC Sensor Sheet** | 1 | 100-point flexible capacitive sensor array | Fabricate from gerbers (included) |
| **Jumper Wires** | — | For UART and power (if needed) | — |

---

## 2. PCB Overview

The iCE40HX8K system consists of two PCBs:

 Main Shield PCB (`PCB_ICE40HX8K/`)
This board mounts directly on top of the iCE40HX8K breakout board. It contains the RC charge/discharge circuits and FPC connectors for the sensor sheet.

<p align="center">
  <img width="739" height="652" alt="image" src="https://github.com/user-attachments/assets/bb89477d-a7b1-4b99-b3d5-1fe461921570" />
</p>

**Key features:**
- 100x 0402 SMD resistors (10 MΩ) forming RC networks
- 2x 50-pin FPC connectors for the sensor array
- 4-layer design for signal integrity and low crosstalk
- Mounting holes aligned to the iCE40HX8K breakout board
---

## 3. Step-by-Step Assembly

### Step 1: Solder the Resistors
You will solder **100 resistors** onto the main shield PCB.

- **Package:** 0402 (very small — use tweezers and a fine-tip iron)
- **Value:** 10 MΩ each
- **Placement:** Refer to the silkscreen labels (R1, R2, ... R100)

> **Tip:** Solder in batches of 10 and check with a multimeter to avoid bridged joints.

### Step 2: Solder the FPC Connectors
Solder the two **50-pin FPC connectors** onto the shield PCB.

- **Part:** Würth Elektronik 687150149022
- **Orientation:** Bottom contact (the flexible cable inserts with the conductive pads facing down)
- **Alignment:** Match the notch on the connector to the silkscreen outline

<p align="center">
  <img width="640" height="640" alt="image" src="https://github.com/user-attachments/assets/93399ff6-0ff3-42b2-a0dc-0228e85a1ea9" />

</p>

### Step 3: Inspect Your Work
Before powering on:
1. Check for solder bridges between adjacent 0402 pads
2. Verify all 100 resistors are present
3. Ensure FPC connectors are flat and fully seated

### Step 4: Mount the Shield onto the iCE40HX8K
Align the shield PCB with the iCE40HX8K breakout board headers and press firmly to seat all pins.

---

## 4. Connecting the Sensor
Connect the sensors

---

## 5. Firmware Setup (`cap_test4/`)

### Prerequisites
Install the open-source FPGA toolchain:
- [Yosys](https://github.com/YosysHQ/yosys) — synthesis
- [nextpnr](https://github.com/YosysHQ/nextpnr) — place & route
- [IceStorm](https://github.com/YosysHQ/icestorm) — bitstream tools

### Project Structure
cap_test4/
├── src/
     ├── top.v                 # Top-level module
     ├── cap_sensor.v         
     ├── pins.pcf       
     ├── Makefile    
     └── uart_tx.v             # UART output (2 Mbaud)

### Build the Bitstream
1. cd cap_test4
2. make clean
3. make flash

### Visuliztion 
