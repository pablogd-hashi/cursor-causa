service {
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
    http     = "http://127.0.0.1:8080/healthz"
    interval = "10s"
    timeout  = "3s"
  }
}
