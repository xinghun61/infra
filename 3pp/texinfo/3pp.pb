create {
  platform_re: ".*-arm.*|.*-mips.*"
  unsupported: true
}

create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/texinfo"
      default_version: "6.5"
      original_download_url: "https://ftp.gnu.org/gnu/texinfo/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
