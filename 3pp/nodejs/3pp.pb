create {
  # mac, windows, linux 64bit, linux arm 32/64
  platform_re: ".*amd64|.*arm.*"
  source {
    script { name: "fetch.py" }
    unpack_archive: true
  }
}

upload {
  pkg_prefix: "tools"
}

