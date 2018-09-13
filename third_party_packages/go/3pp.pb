create {
  source {
    script { name: "fetch.py" }
    unpack_archive: true
    no_archive_prune: true
  }
  build {}
}

upload { pkg_prefix: "infra" }
