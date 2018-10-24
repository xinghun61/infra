create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/gettext"
      default_version: "0.19.8"
      original_download_url: "https://ftp.gnu.org/pub/gnu/gettext/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
