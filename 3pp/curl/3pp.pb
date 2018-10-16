create {
  platform_re: "linux-.*|mac-.*"

  source {
    cipd {
      pkg: "infra/third_party/source/curl"
      default_version: "7.59.0"
    }
    unpack_archive: true
  }

  build {
    dep: "zlib"
    dep: "libidn2"
  }
}

create {
  platform_re: "linux-.*"

  build {
    dep: "zlib"
    dep: "libidn2"
    dep: "openssl"
  }
}

upload { pkg_prefix: "infra/third_party/static_libs" }
