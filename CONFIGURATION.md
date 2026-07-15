# Comfee IR Integration Configuration

This integration generates Comfee AC Tuya IR payloads on demand and sends them directly to your transmitter text entity via `text.set_value`.

## Required

- A transmitter text entity, for example:
  - `text.ir_code_to_send`

## Options

- `infrared_emitter_entity_id` (required): Home Assistant infrared emitter entity that will transmit the commands.
- `name` (optional, default `Comfee IR`)

## Supported Modes

- HVAC: `off`, `cool`, `dry`, `auto`, `fan_only`
- Fan by mode:
  - `cool`: `auto`, `low`, `high`
  - `dry`: `low`
  - `auto`: `low`
  - `fan_only`: `auto`, `low`, `high`

## How It Works

1. Climate state change triggers command generation.
2. Integration builds the IR frame + inverted frame.
3. Payload is encoded with Tuya stream compression using the same codec logic as the integration.
4. Base64 payload is sent to your transmitter text entity using `text.set_value`.

## Troubleshooting

- `Failed to send IR command ...`
  - Check entity exists in Developer Tools -> States.
  - Confirm `text.set_value` works manually with your transmitter entity.
- AC does not react:
  - Verify transmitter is actually sending Tuya payloads from that text field.
  - Check line-of-sight and transmitter logs.
