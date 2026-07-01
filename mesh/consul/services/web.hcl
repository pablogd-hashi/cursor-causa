service {
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
    http     = "http://127.0.0.1:9090/health"
    interval = "10s"
    timeout  = "3s"
  }
}
