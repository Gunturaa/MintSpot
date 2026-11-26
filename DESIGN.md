# MintSpot — Design Direction

## Identity
- **Product:** MintSpot — Personal 5 GHz Wi-Fi Bridge for Linux Mint.
- **Problem solved:** Keeps the laptop connected to a 2.4 GHz Wi-Fi network while broadcasting a 5 GHz hotspot via Wi-Fi Direct (`P2P-GO`) for 5 GHz-only iOS devices.
- **Personality:** Calm, tactile, native system utility inspired by macOS Sequoia System Settings and iOS Personal Hotspot.

## Visual Palette (WCAG AA Verified)
Strict 2-neutral + 1-accent system with working Light and Dark themes.

### Light Mode (Default)
- **Canvas (`systemGroupedBackground`):** `#F2F2F7`
- **Inset Card Surface:** `#FFFFFF` (hairline border `rgba(60, 60, 67, 0.14)`)
- **Primary Text:** `#1C1C1E` (17.01:1 on `#FFFFFF`, 15.25:1 on `#F2F2F7`)
- **Secondary Text:** `#5A5A5E` (6.87:1 on `#FFFFFF`, 6.15:1 on `#F2F2F7`)
- **Primary Accent:** `#0066CC` (5.57:1 with `#FFFFFF`)
- **Active Status:** `#187032` text on `#E6F5EA` pill (5.47:1)
- **Destructive Action:** `#C92A2A` on `#FFFFFF` (5.46:1)

### Dark Mode
- **Canvas:** `#1C1C1E`
- **Inset Card Surface:** `#2C2C2E` (hairline border `rgba(255, 255, 255, 0.10)`)
- **Primary Text:** `#F5F5F7` (12.80:1 on `#2C2C2E`, 15.63:1 on `#1C1C1E`)
- **Secondary Text:** `#AEAEB2` (6.30:1 on `#2C2C2E`, 7.69:1 on `#1C1C1E`)
- **Primary Accent:** `#64B5FF` on `#2C2C2E` (6.37:1); `#FFFFFF` on `#0066CC` buttons (5.57:1)
- **Active Status:** `#6EE787` text on `#1A3322` pill (8.73:1)
- **Destructive Action:** `#FF7B72` on `#2C2C2E` (5.53:1)

## Radii & Surface Rules
- Inset grouped cards: `12px` radius, flat elevation with hairline border.
- Primary/secondary buttons and inputs: `8px`–`10px` radius.
- Pill radius (`999px`): reserved strictly for status badges and Apple-style toggle switches.
- Zero decorative gradients, zero glow effects, zero emoji in UI chrome.
- Focus rings: explicit `2px solid` high-contrast `:focus-visible` outline on all interactive controls.

## Signature Component
- **Signal Bridge Card:** A two-node horizontal status strip showing the live `Uplink (2.4 GHz)` -> `Hotspot (5 GHz P2P)` bridge path alongside a dedicated **iPhone 5 GHz Bridge** switch that locks `method=p2p` and `band=a`.
