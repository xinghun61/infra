create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/openssl"
      default_version: "1.1.1"
      original_download_url: "https://www.openssl.org/source/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
