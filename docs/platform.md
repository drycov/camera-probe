# Platform role: camera-probe

`camera-probe` is the **shared library** for IP camera / NVR discovery and protocol probing in the ops ecosystem.

Profile map: [github.com/drycov — Ops platform ecosystem](https://github.com/drycov#-ops-platform-ecosystem)

## Position in the stack

```text
camera-probe  ──►  inventory / jobs  ──►  cms · equipment-bot · (other products)
     ▲
     └── only place for RTSP/HTTP/ONVIF vendor probe implementation
```

## Consumers (intended)

| Product | How it should use this library |
| --- | --- |
| [cms](https://github.com/drycov/cms) | Discovery, identity, health probes for camera inventory |
| [equipment-bot](https://github.com/drycov/equipment-bot) | Field inventory enrichment, avoid local duplicate probes |
| backup_tool / others | Only if camera probing is required — depend here, do not copy |

## Non-goals

- Not a full VMS
- Not an equipment registry / CMDB UI
- Not Cerebro business sync (that stays in inventory adapters)
- Not MikroTik/SNMP network core (separate concern)

## Contract for product repos

1. Use public API: `probe()`, `scan()`, `ProbeResult` (see root README).
2. Do not re-implement ONVIF/Hikvision/Dahua discovery next to this package.
3. Vendor-specific **authenticated** snapshot helpers in products should call into or gradually migrate toward this library when APIs overlap.
4. File issues here for protocol bugs; file product UX issues in consumer repos.

## Versioning note

Prefer pinned releases from PyPI (`pip install camera-probe`) in production products. Editable path installs are fine for local platform development.
