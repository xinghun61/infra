create {
  platform_re: "linux-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/openssl"
      default_version: "1.1.0f"
    }
    unpack_archive: true
  }
  build {}
}

# On mac we actually build with the 'headers' version of openssl because we
# need the OS X openssl integration goodness.
create {
  platform_re: "mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/openssl"
      default_version: "0.9.8zh"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "infra/third_party/static_libs" }
