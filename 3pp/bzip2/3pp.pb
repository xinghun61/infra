create {
  platform_re: "linux-.*|mac-.*"
  source {
    cipd {
      pkg: "infra/third_party/source/bzip2"
      default_version: "1.0.6"

      # Note that the original bzip.org site seems to be pretty hosed. This also
      # hasn't been updated since 2010, and it seems unlikely that anyone will
      # ever update it.
      original_download_url: "http://www.bzip.org/1.0.6/bzip2-1.0.6.tar.gz"
    }
    unpack_archive: true
  }
  build {}
}

upload { pkg_prefix: "static_libs" }
