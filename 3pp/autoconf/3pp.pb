create {
  platform_re: "linux-amd64|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/autoconf"
      default_version: "2.69"
    }
    unpack_archive: true
    patch_dir: "patches"
    patch_version: "chromium1"
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/tools" }
