create {
  source { script { name: "fetch.py" } }
  build {}
}

upload {
  pkg_prefix: "infra/third_party/build_support"
}
