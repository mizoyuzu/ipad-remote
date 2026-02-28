# Binary Protocol Specification

## Overview

6-byte fixed-length UDP packets, little-endian.

## Packet Format

| Offset | Type   | Name    | Description                          |
|--------|--------|---------|--------------------------------------|
| 0      | uint8  | mode    | 0=trackpad, 1=scroll, 2=arrow       |
| 1      | uint8  | flags   | Mode-dependent bit flags             |
| 2      | int8   | dx      | Horizontal delta (-128..127)         |
| 3      | int8   | dy      | Vertical delta (-128..127)           |
| 4      | int8   | wheel   | Scroll wheel delta (-128..127)       |
| 5      | uint8  | keycode | USB HID keycode (0x00 = none)        |

## Flags Byte

### Mode 0 (Trackpad) — Mouse buttons
| Bit | Meaning      |
|-----|--------------|
| 0   | Left button  |
| 1   | Right button |
| 2   | Middle button|

### Mode 1 (Scroll) — Unused (0x00)

### Mode 2 (Arrow) — Keyboard modifiers
| Bit | Meaning    |
|-----|------------|
| 0   | Left Ctrl  |
| 1   | Left Shift |
| 2   | Left Alt   |
| 3   | Left GUI (Cmd) |

## Keycodes

| Action         | keycode | flags | Notes               |
|----------------|---------|-------|---------------------|
| None           | 0x00    | 0x00  | Movement-only / release |
| Enter          | 0x28    | 0x00  | Tap in arrow mode   |
| Right Arrow    | 0x4F    | 0x00  |                     |
| Left Arrow     | 0x50    | 0x00  |                     |
| Down Arrow     | 0x51    | 0x00  |                     |
| Up Arrow       | 0x52    | 0x00  |                     |
| Home (Cmd+H)   | 0x0B    | 0x08  | GUI + H             |
| App Switch     | 0x2B    | 0x08  | GUI + Tab           |

## Key Release Protocol

After every key press, send a follow-up packet with `keycode=0x00` and `flags=0x00`
within the same mode to signal key release (typically after 50ms delay).

## Struct Formats

- **Python**: `struct.Struct('<BBbbbB')`
- **Swift**: Manual `Data` assembly (see Packet.swift)

## Network

- Transport: UDP
- Port: 5005
- mDNS service type: `_ipadremote._udp`
