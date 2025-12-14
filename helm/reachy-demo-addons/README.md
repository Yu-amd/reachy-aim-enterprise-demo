# Reachy Demo Add-ons Helm Chart

This chart deploys add-ons for the Reachy Mini + AIM enterprise demo:
- **Load generator** (CronJob) - Generates load against AIM endpoint
- **Grafana dashboard** (ConfigMap) - Pre-configured dashboard for monitoring
- **Optional monitoring stack** - kube-prometheus-stack (if needed)

## URL-Mode Configuration

This chart uses **URL-mode** configuration, meaning it connects to AIM endpoints via direct URLs rather than Kubernetes Service discovery. This provides maximum flexibility:

- Works with external AIM endpoints (outside cluster)
- Works with cluster-internal AIM services (via Service URL)
- Works with port-forwarded endpoints
- No assumptions about Service names or ports

### Configuration

Set `aim.baseUrl` to your AIM endpoint URL:

```yaml
aim:
  baseUrl: "http://aim.default.svc.cluster.local:8000"  # Cluster-internal
  # OR
  baseUrl: "https://aim.example.com"  # External
  # OR
  baseUrl: "http://localhost:8000"  # Port-forward (if loadgen runs locally)
  chatPath: "/v1/chat/completions"
  model: "llm-prod"
```

## Monitoring

### If your cluster already has monitoring

Set `monitoring.installKubePromStack=false` (default) and just use the dashboard ConfigMap:

```yaml
monitoring:
  enabled: true
  installKubePromStack: false  # Use existing monitoring
```

The Grafana dashboard ConfigMap will be created and can be imported into your existing Grafana instance.

### If you need to install monitoring

Set `monitoring.installKubePromStack=true` to install kube-prometheus-stack:

```yaml
monitoring:
  enabled: true
  installKubePromStack: true  # Install monitoring stack
  namespace: monitoring
```

**Note:** This will install the full Prometheus + Grafana stack, which may conflict with existing monitoring. Only use if you don't have monitoring already.

## Environment Variable Consistency

The load generator uses the same environment variable names as the edge client for consistency:

- `AIM_BASE_URL` - AIM endpoint URL
- `AIM_CHAT_PATH` - Chat completions path (default: `/v1/chat/completions`)
- `AIM_MODEL` - Model name (default: `llm-prod`)
- `AIM_API_KEY` - Optional API key (from Secret if enabled)

This ensures the same configuration works for both edge client and cluster load generator.

