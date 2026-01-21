# **DD-WRT Integration for Home Assistant**

A robust, asynchronous custom component for DD-WRT routers, providing sensors and device tracking via the .live.asp polling interface.

Note: This integration was vibe coded with Gemini

## **Features**

* **Sensors:** WAN IP, Uptime, Load Average, Traffic (In/Out), Memory (Free/Used), CPU Temperature.  
* **Device Tracking:** Tracks devices connected to WiFi and wired interfaces (via ARP/DHCP).  
* **Config Flow:** Easy setup via UI with auto-detection of interfaces.  
* **Performance:** Uses aiohttp for non-blocking I/O.

## **Installation**

### **Via HACS (Recommended)**

1. Ensure [HACS](https://hacs.xyz/) is installed.  
2. Add this repository as a custom repository:  
   * URL: https://github.com/kylehase/home-assistant-ddwrt  
   * Type: Integration  
3. Click Install.  
4. Restart Home Assistant.

### **Manual Installation**

1. Copy the custom\_components/ddwrt directory to your Home Assistant config/custom\_components/ directory.  
2. Restart Home Assistant.

## **Configuration**

1. Go to **Settings** \> **Devices & Services**.  
2. Click **Add Integration**.  
3. Search for **DD-WRT**.  
4. Follow the configuration steps:  
   * **Step 1:** Enter Router IP and optional Port (defaults to 80/443).  
   * **Step 2:** Enter Username (usually root) and Password.  
   * **Step 3:** Enter a friendly name (e.g., skynet) and select which network interfaces to monitor for device tracking.

## **Debugging**

If you run into issues, enable debug logging in your configuration.yaml:

logger:  
  default: info  
  logs:  
    custom\_components.ddwrt: debug

## **Troubleshooting**

* **Entities not showing up:** The integration only enables entities for which data is returned by the router. If your router model doesn't report CPU temperature, that sensor will not be created.  
* **Connection Failed:** Ensure Info.live.htm and Statusinfo.live.asp are accessible from your Home Assistant instance.