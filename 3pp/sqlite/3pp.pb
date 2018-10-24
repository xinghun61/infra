create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/sqlite-autoconf"
      default_version: "3.19.3"
      original_download_url: "https://www.sqlite.org/download.html"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
