datacenter = "dc1"
data_dir   = "/consul/data"
log_level  = "INFO"

# Single-server dev stack. ACLs off for the demo; see docs/consul-mesh.md for
# production hardening (mTLS, ACLs, Vault PKI Connect CA).
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

# ── Mesh topology: web → api → [payments, cache]; payments → currency → rates ──
# rates is external (no Connect) and reached via the Terminating Gateway.

services {
  name = "web"
  id   = "web-1"
  port = 9090
  tags = ["v1", "frontend", "mesh"]

  connect {
    sidecar_service {
      proxy {
        mode = "transparent"
      }
    }
  }

  check {
    http     = "http://web:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}

services {
  name = "api"
  id   = "api-1"
  port = 9090
  tags = ["v1", "backend", "mesh"]

  connect {
    sidecar_service {
      proxy {
        mode           = "transparent"
        upstreams = [
          { destination_name = "payments" local_bind_port = 19080 },
          { destination_name = "cache" local_bind_port = 19091 },
        ]
      }
    }
  }

  check {
    http     = "http://api:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}

services {
  name = "payments"
  id   = "payments-1"
  port = 8080
  tags = ["v1", "backend", "mesh", "causa-demo"]

  connect {
    sidecar_service {
      proxy {
        mode = "transparent"
        upstreams = [
          { destination_name = "currency" local_bind_port = 19092 },
        ]
      }
    }
  }

  check {
    http     = "http://demo-app:8080/healthz"
    interval = "10s"
    timeout  = "3s"
  }
}

services {
  name = "currency"
  id   = "currency-1"
  port = 9090
  tags = ["v1", "backend", "mesh"]

  connect {
    sidecar_service {
      proxy {
        mode = "transparent"
      }
    }
  }

  check {
    http     = "http://currency:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}

services {
  name = "cache"
  id   = "cache-1"
  port = 9090
  tags = ["v1", "backend", "mesh"]

  connect {
    sidecar_service {
      proxy {
        mode = "transparent"
      }
    }
  }

  check {
    http     = "http://cache:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}

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
