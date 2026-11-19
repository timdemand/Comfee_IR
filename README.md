# Comfee IR Climate (Remote)

Custom Home Assistant integration for generating Comfee IR commands and sending them through a native Home Assistant infrared emitter entity.

Repository: https://github.com/timdemand/Comfee_IR

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=timdemand&repository=Comfee_IR&category=integration)

## Installation

### Via Home Assistant Marketplace (Home Assistant 2026.11+)

1. Click the **My Home Assistant** badge above, or navigate to **Settings > Marketplace** in your Home Assistant instance.
2. In the top right corner, open the menu (three dots) and select **Custom repositories**.
3. Add `https://github.com/timdemand/Comfee_IR` with category **Integration**.
4. Find **Comfee IR** in the Marketplace and click **Install**.
5. Restart Home Assistant if prompted.

### Via Legacy HACS

1. Open **HACS** > **Integrations**.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add `https://github.com/timdemand/Comfee_IR` as type **Integration**.
4. Download the repository and restart Home Assistant.

## Configuration

After installation:
1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **Comfee IR**.
3. Select your native Home Assistant infrared emitter entity (`infrared` domain).
