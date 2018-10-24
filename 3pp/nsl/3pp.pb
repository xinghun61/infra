create {
  # Only used on linux
  platform_re: "linux-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/nsl"
      default_version: "1.0.4"
      original_download_url: "https://github.com/thkukuk/libnsl/releases"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
