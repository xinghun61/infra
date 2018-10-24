create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/gnu_sed"
      default_version: "4.2.2"
      original_download_url: "https://ftp.gnu.org/gnu/sed/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
