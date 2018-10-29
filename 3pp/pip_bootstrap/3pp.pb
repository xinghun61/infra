create {
  platform_re: "windows-.*"
  unsupported: true
}

create {
  source { script { name: "fetch.py" } }
  build {}
}

upload {
  pkg_prefix: "build_support"
  universal: true
}
