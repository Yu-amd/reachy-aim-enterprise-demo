# Architecture Overview

## System Components

```
┌─────────────────┐          ┌──────────────────┐         ┌─────────────────┐
│                 │          │                  │         │                 │
│  Reachy Mini    │────────▶│   AIM Endpoint    │────────▶│  LLM Inference │
│  (Edge Client)  │  HTTP    │  (OpenAI-compat) │         │  (MI300X/Cloud) │
│                 │          │                  │         │                 │
└─────────────────┘          └──────────────────┘         └─────────────────┘
       │                              │
       │                              │
            ▼                                                    ▼
┌─────────────────┐         ┌──────────────────┐
│                 │         │                  │
│  Robot Control  │         │  Load Generator  │
│  (Gestures/TTS) │         │  (K8s CronJob)   │
│                 │         │                  │
└─────────────────┘         └──────────────────┘
       │                              │
       └──────────────┬───────────────┘
                      │
                                      ▼
            ┌──────────────────┐
            │                  │
            │  Prometheus +    │
            │  Grafana         │
            │  (Metrics)       │
            │                  │
            └──────────────────┘
```

## Component Responsibilities

### Edge Client (Reachy Mini)
- **Location**: Runs on edge device (Strix Halo host)
- **Responsibilities**:
  - User interaction (CLI input/output)
  - Robot control (gestures, state queries)
  - AIM API client (OpenAI-compatible requests)
  - Metrics collection (Prometheus metrics export)
  - Latency monitoring (end-to-end SLO tracking)

### AIM Endpoint
- **Location**: Datacenter/cloud (e.g., MI300X cluster)
- **Responsibilities**:
  - LLM inference (OpenAI-compatible API)
  - Model serving
  - Request handling and response generation

### Kubernetes Add-ons
- **Location**: Kubernetes cluster
- **Components**:
  - **Load Generator**: CronJob that sends periodic load to AIM endpoint
  - **Grafana Dashboard**: ConfigMap with pre-configured dashboards
  - **Prometheus**: Scrapes edge metrics (optional, via kube-prometheus-stack)

## Data Flow

1. **User Interaction**:
   - User types prompt in edge client
   - Edge client sends request to AIM endpoint
   - AIM endpoint processes with LLM
   - Response returned to edge client
   - Edge client displays response and triggers robot gesture

2. **Load Testing**:
   - Kubernetes CronJob triggers load generator
   - Load generator sends concurrent requests to AIM endpoint
   - Metrics collected and exposed via Prometheus

3. **Monitoring**:
   - Edge client exports Prometheus metrics
   - Prometheus scrapes metrics
   - Grafana visualizes metrics from dashboards

## Key Design Decisions

- **Separation of Concerns**: Edge handles I/O, cloud handles compute
- **OpenAI Compatibility**: AIM endpoint uses OpenAI API format for easy integration
- **Simulation-First**: Works without physical robot using daemon simulation
- **URL-Based Configuration**: Helm chart uses URLs (not Service discovery) for flexibility
- **Metrics-Driven**: Prometheus metrics for observability and SLO tracking

