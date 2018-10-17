create {
  source { script { name: "fetch.py" } }
  build {}
}

upload {
  pkg_prefix: "build_support"
}
