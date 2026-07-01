datacenter = "dc1"
data_dir   = "/consul/data"
log_level  = "INFO"

server           = true
bootstrap_expect = 1

bind_addr   = "0.0.0.0"
client_addr = "0.0.0.0"

ui_config {
  enabled = true

  metrics_provider = "prometheus"
  metrics_proxy {
    base_url = "http://prometheus:9090"
  }

  dashboard_url_templates {
    service = "http://localhost:3000/d/service-to-service?orgId=1&var-service={{Service.Name}}"
  }
}

connect {
  enabled = true
}

telemetry {
  prometheus_retention_time = "10m"
  disable_hostname          = true
}

ports {
  http = 8500
  grpc = 8502
  dns  = 8600
}

# Mesh apps (web, api, payments) register on their local Connect agents.
# The server only runs the catalog — no app services defined here.
