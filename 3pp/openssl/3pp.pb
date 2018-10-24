create {
  platform_re: "linux-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/openssl"
      default_version: "1.1.1"
      original_download_url: "https://www.openssl.org/source/"
    }
    unpack_archive: true
  }
  build {}
}

# On mac we actually build with the 'headers' version of openssl because we
# need the OS X openssl/Keychain integration.
create {
  platform_re: "mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/openssl"
      default_version: "0.9.8zh"
      original_download_url: "https://www.openssl.org/source/old"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
