service {
  name = "api"
  id   = "api-1"
  port = 9090
  tags = ["v1", "backend", "mesh"]

  connect {
    sidecar_service {
      proxy {
        mode = "transparent"
        upstreams = [
          { destination_name = "payments" local_bind_port = 19080 },
          { destination_name = "cache" local_bind_port = 19091 },
        ]
      }
    }
  }

  check {
    http     = "http://127.0.0.1:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}
