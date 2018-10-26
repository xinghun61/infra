create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/help2man"
      default_version: "1.47.8"
      original_download_url: "https://ftp.gnu.org/gnu/help2man/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "tools" }

