create {
  platform_re: "windows-amd64"
  source {
    script { name: "fetch_win.py" }
    unpack_archive: true
  }
}

upload { pkg_prefix: "tools" }
