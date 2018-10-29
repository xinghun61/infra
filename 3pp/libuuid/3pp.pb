create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      # libuuid is part of util-linux
      pkg: "infra/third_party/source/util-linux"
      default_version: "2.33-rc1"
      original_download_url: "https://mirrors.edge.kernel.org/pub/linux/utils/util-linux/v2.33/"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }

