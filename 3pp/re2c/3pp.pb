create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/re2c"
      default_version: "1.1.1"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/tools" }
