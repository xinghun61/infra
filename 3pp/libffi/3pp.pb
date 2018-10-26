create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/libffi"
      default_version: "3.2.1"
      original_download_url: "https://github.com/libffi/libffi/releases"
    }
    unpack_archive: true
  }
  build {
    tool: "autoconf"
    tool: "automake"
    tool: "libtool"
    tool: "texinfo"
  }
}

upload { pkg_prefix: "static_libs" }
