create {
  # Only used on linux
  platform_re: "linux-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/nsl"
      default_version: "1.0.4"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
