# DD-WRT Integration for Home Assistant

A robust, asynchronous custom component for DD-WRT routers, providing sensors, binary sensors, buttons, and device tracking via the `.live.asp` polling interface.

## Features

### v1.1.0 Highlights

* **Real-Time Bandwidth:** New sensors for Download and Upload speeds (kB/s).

* **Router Control:** New **Reboot** button entity.

* **Optimized Polling:** Now polls only 4 essential endpoints to reduce router load.

### Core Features

* **Sensors:**

  * **System:** Uptime, CPU Load Average (1m, 5m, 15m), CPU Temperature.

  * **Memory:** Total, Free, and Used Percentage.

  * **Network:** WAN IP, WAN Protocol, Router IP Info, WAN Uptime (Days).

  * **Traffic:** Total Traffic In/Out (MB) and Real-time Rates (kB/s).

  * **Wireless:** Active Client Count.

  * **Dynamic:** Automatically creates read-only sensors for other supported keys found in your router's data.

* **Binary Sensors:**

  * **WAN Status:** Connectivity state.

  * **Wireless Radio:** Radio active/inactive state.

* **Buttons:**

  * **Reboot Router:** Safely reboot the router from Home Assistant.

* **Device Tracking:** Tracks devices connected to WiFi and wired interfaces (via ARP/DHCP).

* **Config Flow:** Easy setup via UI with auto-detection of interfaces (e.g., `br0`, `eth1`, `wl0`).

## Installation

### Via HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.

2. Add this repository as a custom repository:

   * URL: `https://github.com/kylehase/home-assistant-ddwrt`

   * Type: `Integration`

3. Click Install.

4. Restart Home Assistant.

### Manual Installation

1. Copy the `custom_components/ddwrt` directory to your Home Assistant `config/custom_components/` directory.

2. Restart Home Assistant.

## Configuration

1. Go to **Settings** > **Devices & Services**.

2. Click **Add Integration**.

3. Search for **DD-WRT**.

4. Follow the configuration steps:

   * **Step 1:** Enter Router IP and optional Port (defaults to 80, then tries 443).

   * **Step 2:** Enter Username (usually `root`) and Password.

   * **Step 3:** Enter a friendly name (e.g., `skynet`) and select which network interfaces to monitor for device tracking.

## Troubleshooting & Debugging

* **Missing Entities:**

  * If a sensor (like CPU Temperature) is not supported by your specific router hardware, the entity will be created but **disabled** by default to prevent "Unavailable" clutter.

  * You can enable these entities manually in **Settings > Devices & Services > DD-WRT > Entities** if you believe data should be present.

  * Entities with values like "N/A", "Unknown", or empty strings during setup are also automatically disabled.

* **Connection Failed:**

  * Ensure the router IP is correct and reachable from your Home Assistant instance.

  * Verify that your router credentials are correct (default user is often `root`).

* **Enable Debug Logging:**
  To see exactly what data your router is returning, add this to your `configuration.yaml`: