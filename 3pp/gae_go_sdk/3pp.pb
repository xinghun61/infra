create {
  platform_re: ".*-386|.*-amd64"
  source {
    script { name: "fetch.py" }
    unpack_archive: true
  }
}

upload {
  pkg_prefix: "tools"
}
