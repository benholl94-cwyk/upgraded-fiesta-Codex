# Mobile device manifest exporter

`scripts/export_device_manifest.swift` prints a JSON manifest for the current Apple/mobile host without writing host-specific data into the repository.

Run it from the repository root with Swift available:

```sh
swift scripts/export_device_manifest.swift
```

The manifest includes:

- `manifestVersion`, currently `1.0.0`.
- `device`, a sorted JSON object containing schema version, timestamp, host name, OS description, CPU core count, physical memory, and uptime.
- `integrityHash`, a SHA-256 digest calculated from the canonical pretty-printed/sorted `device` JSON payload.

Use the printed output as an ephemeral diagnostics artifact. Do not commit generated manifests when they identify a private device or host.
