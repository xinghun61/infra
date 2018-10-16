create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/pcre"
      default_version: "8.41"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
