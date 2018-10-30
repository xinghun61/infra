create {
  platform_re: ".*-arm.*|.*-mips.*"
  unsupported: true
}

create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/binutils"
      default_version: "2.31"
      original_download_url: "https://ftp.gnu.org/gnu/binutils/"
    }
    unpack_archive: true
  }
  build {
    tool: "texinfo"
  }
}

upload { pkg_prefix: "tools" }
