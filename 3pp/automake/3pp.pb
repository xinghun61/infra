create {
  platform_re: "linux-.*|mac-.*"

  source {
    cipd {
      pkg: "infra/third_party/source/automake"
      default_version: "1.15"
    }
    unpack_archive: true
    patch_dir: "patches"
    patch_version: "chromium1"
  }

  build { tool: "autoconf" }
}

upload { pkg_prefix: "infra/third_party/tools" }
