create {
  platform_re: "linux-amd64|mac-amd64"
  source {
    script { name: "fetch.py" }
    patch_version: "chromium0"
    unpack_archive: true
    no_archive_prune: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
