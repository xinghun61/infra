create {
  source {
    script { name: "fetch.py" }
    unpack_archive: true
  }
}

upload { pkg_prefix: "tools" }
