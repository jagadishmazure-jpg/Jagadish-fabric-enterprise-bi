# `modules/streaming`

Event Hubs namespace with local (SAS) auth off, a POS hub with an Eventstream consumer group (Standard and above; Basic has only the default group), Data Receiver for the ingest identity, and an IoT Hub with an Eventstream consumer group; diagnostics to Log Analytics.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | Resources |
| [`outputs.tf`](outputs.tf) | Values returned to the root stack |
| [`variables.tf`](variables.tf) | Inputs with types, defaults and validation |
| [`versions.tf`](versions.tf) | Provider constraints |
