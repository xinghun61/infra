create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/readline"
      default_version: "7.0"
      original_download_url: "https://ftp.gnu.org/gnu/readline/"
    }
    unpack_archive: true
  }
  build {
    dep: "ncurses"
  }
}

upload { pkg_prefix: "static_libs" }
