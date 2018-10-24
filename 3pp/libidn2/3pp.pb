create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/libidn2"
      default_version: "2.0.4"
      original_download_url: "https://ftp.gnu.org/gnu/libidn/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
