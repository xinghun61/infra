create {
  source {
    script { name: "fetch.py" }
    patch_version: "chromium0"
    unpack_archive: true
    no_archive_prune: true
  }
  build {}
}

upload { pkg_prefix: "tools" }
