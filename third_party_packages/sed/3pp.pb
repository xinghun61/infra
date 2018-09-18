create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/gnu_sed"
      default_version: "4.2.2"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/tools" }
