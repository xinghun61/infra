create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/zlib"
      default_version: "1.2.11"
      original_download_url: "https://zlib.net/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
