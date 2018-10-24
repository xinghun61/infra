create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/re2c"
      default_version: "1.1.1"
      original_download_url: "https://github.com/skvadrik/re2c/releases"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
