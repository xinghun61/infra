create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/libidn2"
      default_version: "2.0.4"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
