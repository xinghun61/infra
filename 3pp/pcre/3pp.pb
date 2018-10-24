create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/pcre"
      default_version: "8.41"
      original_download_url: "https://ftp.pcre.org/pub/pcre/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
