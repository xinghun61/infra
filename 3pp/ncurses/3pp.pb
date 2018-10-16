create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/ncurses"
      default_version: "6.0"
    }
    unpack_archive: true
    patch_dir: "patches"
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
