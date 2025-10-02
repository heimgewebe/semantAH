# Observability Runbook

## Overview

This runbook describes how to access the local observability stack while developing semantAH. The stack is composed of Grafana, Loki, and Tempo containers that expose HTTP interfaces for debugging and tracing.

## Endpoints

- Grafana: [http://localhost:3000](http://localhost:3000)
- Loki: [http://localhost:3100](http://localhost:3100)
- Tempo: [http://localhost:3200](http://localhost:3200)

Use these endpoints to inspect logs, metrics, and traces when diagnosing issues in the development environment.
