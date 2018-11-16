create {
  source { script { name: "fetch.py" } }
  build {
    no_docker_env: true
  }
}

upload {
  pkg_prefix: "build_support"
  universal: true
}
