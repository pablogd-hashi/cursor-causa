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

# Gateways and external rates stay on the server; mesh apps register locally.
services {
  name = "api-gateway"
  id   = "api-gateway-1"
  port = 21001
  tags = ["gateway", "ingress", "api-gateway"]

  check {
    http     = "http://api-gateway:20201/ready"
    interval = "10s"
    timeout  = "3s"
  }
}

services {
  name = "terminating-gateway"
  id   = "terminating-gateway-1"
  port = 9190
  tags = ["gateway", "terminating", "egress"]
}

services {
  name = "rates"
  id   = "rates-1"
  port = 9090
  tags = ["v1", "external", "rates"]

  check {
    http     = "http://rates:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}
