create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/xzutils"
      default_version: "5.2.4"
      original_download_url: "https://tukaani.org/xz/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
