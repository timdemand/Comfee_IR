# Comfee IR Integration Configuration

This integration generates Comfee AC IR payloads and transmits them through a native Home Assistant infrared emitter entity (`infrared` domain).

## Required

- A Home Assistant infrared emitter entity, for example:
  - `infrared.ir_emitter` (or any entity under the `infrared` domain)

## Setup Options

- `infrared_emitter_entity_id` (required): The Home Assistant infrared emitter entity that transmits the commands.
- `name` (optional, default: `Comfee IR`): Custom name for the climate device.

## Supported Modes & Capabilities

- **HVAC Modes**: `off`, `cool`, `dry`, `auto`, `fan_only`
- **Fan Modes by HVAC Mode**:
  - `cool`: `auto`, `low`, `high`
  - `dry`: `low`
  - `auto`: `low`
  - `fan_only`: `auto`, `low`, `high`
- **Temperature Range**: 17°C – 30°C
- **Display Button**: Dedicated button entity to toggle the AC's LED display.

## How It Works

1. Changing climate settings (mode, target temperature, fan speed) triggers command generation.
2. The integration constructs the Comfee/Midea A1 semantic frame and checksum byte.
3. Timings are encoded as an `InfraredCommand` with 38 kHz modulation.
4. The command is transmitted via Home Assistant's native `InfraredEmitterConsumerEntity` interface directly to the chosen emitter.

## Troubleshooting

- **No infrared emitter entities available in setup**:
  - Ensure your infrared transmitter hardware integration is installed and configured in Home Assistant providing an entity in the `infrared` domain.
- **AC does not react**:
  - Verify emitter hardware line-of-sight to the Comfee AC unit.
  - Test transmitter operation directly to confirm it is actively emitting signals.
