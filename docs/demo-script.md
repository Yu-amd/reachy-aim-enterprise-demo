# Demo Script

## Enterprise Demo Narrative

This demo showcases an **enterprise edge-to-cloud AI architecture** that enables real-time robot interactions powered by large language models.

### The Story

**Problem**: How do you build an intelligent robot that can understand natural language and respond naturally, without requiring massive compute at the edge?

**Solution**: Separate concerns - edge handles I/O and latency-sensitive robot control, while cloud handles compute-intensive LLM inference.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Edge Device (Laptop)                      │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │ Reachy Mini      │         │ Demo App          │        │
│  │ Daemon           │◄────────┤ (Orchestrator)     │        │
│  │ Port: 8001       │         │                   │        │
│  └──────────────────┘         └────────┬──────────┘        │
│         ▲                              │                    │
│         │ Gestures + TTS               │ HTTP Requests      │
│         │                              ▼                    │
└─────────┼──────────────────────────────┼────────────────────┘
          │                              │
          │                              │
          │                              ▼
┌─────────┼──────────────────────────────┼────────────────────┐
│         │                    ┌─────────▼──────────┐         │
│         │                    │  AIM Endpoint      │         │
│         │                    │  (LLM Inference)   │         │
│         │                    │  Port: 8000/1234   │         │
│         │                    └────────────────────┘         │
│         │                                                    │
│  ┌──────▼──────┐                                            │
│  │  Robot      │                                            │
│  │  (Physical)  │                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Reachy Mini Robot** (Edge)
   - Physical robot with expressive gestures
   - Text-to-speech capabilities
   - Low-latency control via daemon API

2. **Demo Application** (Edge)
   - Orchestrates user interaction
   - Manages conversation context
   - Selects appropriate robot gestures
   - Collects Prometheus metrics

3. **AIM Endpoint** (Cloud/Cluster)
   - OpenAI-compatible LLM inference API
   - Runs on MI300X datacenter GPUs (Mode B)
   - Or local LMStudio for development (Mode A)

### Demo Flow

1. **User asks a question** → Typed into the demo app
2. **Demo app sends to AIM** → HTTP request to LLM endpoint
3. **AIM processes with LLM** → Generates natural language response
4. **Response returns to demo app** → Receives text response
5. **Demo app analyzes response** → Selects appropriate gesture
6. **Robot performs gesture** → Expressive movement (nod, excited, thinking, etc.)
7. **Robot speaks response** → Text-to-speech converts response to audio
8. **Metrics recorded** → Latency, SLO tracking, error rates

### Talking Points

#### For Technical Audiences

- **Edge-Cloud Separation**: Demonstrates how to offload compute-intensive tasks (LLM inference) to the cloud while keeping latency-sensitive operations (robot control) at the edge
- **OpenAI Compatibility**: Uses standard OpenAI API format, making it easy to swap between different LLM providers
- **Observability**: Built-in Prometheus metrics for monitoring latency, SLO compliance, and error rates
- **Production-Ready**: Includes Helm charts for Kubernetes deployment, load generators, and Grafana dashboards

#### For Business Audiences

- **Real-Time AI**: Shows how AI can power natural, real-time interactions with physical devices
- **Scalable Architecture**: Edge devices are lightweight; heavy compute happens in the datacenter
- **Cost-Effective**: Edge devices don't need expensive GPUs; inference happens in shared cloud infrastructure
- **Enterprise-Ready**: Includes monitoring, load testing, and deployment automation

### Demo Scenarios

#### Scenario 1: Simple Question
**User**: "What is machine learning?"  
**Robot**: *[thinking gesture]* "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed."  
**Metrics**: Shows AIM call latency, end-to-end latency, SLO status

#### Scenario 2: Enthusiastic Response
**User**: "That's great!"  
**Robot**: *[excited gesture with antenna wiggle]* "I'm glad you think so! Is there anything else you'd like to know?"  
**Metrics**: Fast response time, positive gesture selection

#### Scenario 3: Agreement
**User**: "Yes, exactly!"  
**Robot**: *[agreeing gesture with multiple nods]* "Perfect! Let's continue."  
**Metrics**: Shows gesture selection based on response content

### Key Metrics to Highlight

- **End-to-End Latency**: Total time from user input to robot response
- **AIM Call Latency**: Time spent in LLM inference
- **SLO Compliance**: Whether responses meet the 2.5 second target
- **Gesture Selection**: How the system chooses appropriate robot expressions

### Closing Points

- **Production-Ready**: This isn't a prototype - it includes monitoring, load testing, and deployment automation
- **Flexible**: Works with any OpenAI-compatible endpoint (AIM, LMStudio, Ollama, etc.)
- **Extensible**: Easy to add new gestures, improve gesture selection, or integrate additional services
- **Open Source**: Apache 2.0 licensed, ready for enterprise use

### Questions to Anticipate

**Q: Why not run the LLM on the edge device?**  
A: LLMs require significant compute resources (GPUs, memory). By running inference in the datacenter, we can use powerful hardware (like MI300X) while keeping edge devices lightweight and cost-effective.

**Q: What about latency?**  
A: The architecture is designed for sub-2.5 second end-to-end latency. Robot control (gestures, TTS) happens instantly at the edge, while only the LLM inference happens in the cloud. Network latency is typically <100ms in modern datacenters.

**Q: Can this scale?**  
A: Yes! The edge devices are stateless and lightweight. The AIM endpoint can scale horizontally in Kubernetes. The Helm chart includes load generators to demonstrate scalability.

**Q: What if the network is down?**  
A: The robot can still perform gestures and basic interactions. LLM inference requires network connectivity, but the edge client gracefully handles failures and retries.

