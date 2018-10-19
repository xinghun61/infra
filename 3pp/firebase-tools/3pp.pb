create {
  # We only have native (no_docker_env) support on amd64 hosts on our build
  # system. Since this is actually creating a universal package, it doesn't
  # matter, but allowing e.g. mac-amd64 and linux-amd64 is convenient for local
  # testing. It should also work on windows too, but *shrug*.
  platform_re: ".*-amd64"

  source {
    script { name: "fetch.py" }
  }
  build {
    tool: "nodejs"

    # Node.js is too new to run under the linux-amd64 docker environment
    # (because that image is based on CentOS5 to conform to PEP 513)
    no_docker_env: true
  }
}

upload {
  pkg_prefix: "npm"
  universal: true
}
