create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/ncurses"
      default_version: "6.0"
      original_download_url: "https://ftp.gnu.org/gnu/ncurses/"
    }
    unpack_archive: true
    patch_dir: "patches"
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
