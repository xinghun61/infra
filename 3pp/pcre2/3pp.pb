create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/pcre2"
      default_version: "10.23"
      original_download_url: "https://ftp.pcre.org/pub/pcre/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
