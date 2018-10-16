create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/bzip2"
      default_version: "1.0.6"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
