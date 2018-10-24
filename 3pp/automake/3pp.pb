create {
  platform_re: "linux-.*|mac-.*"

  source {
    cipd {
      pkg: "infra/third_party/source/automake"
      default_version: "1.15"
      original_download_url: "https://ftp.gnu.org/gnu/automake/"
    }
    unpack_archive: true
    patch_dir: "patches"
    patch_version: "chromium1"
  }

  build { tool: "autoconf" }
}

upload { pkg_prefix: "tools" }
