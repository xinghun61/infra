create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/pcre2"
      default_version: "10.23"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
