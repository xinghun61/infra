create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/readline"
      default_version: "7.0"
    }
    unpack_archive: true
  }
  build {
    dep: "ncurses"
  }
}

upload { pkg_prefix: "infra/third_party/static_libs" }
