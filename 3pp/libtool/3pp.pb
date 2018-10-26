create {
  platform_re: "linux-.*|mac-.*",
  source {
    cipd {
      pkg: "infra/third_party/source/libtool"
      default_version: "2.4.6"
      original_download_url: "https://ftp.gnu.org/pub/gnu/libtool/"
    }
    unpack_archive: true
    patch_dir: "patches"
  }
  build {
    tool: "help2man"
  }
}

upload { pkg_prefix: "tools" }
