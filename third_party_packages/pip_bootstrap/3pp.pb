create {
  source { script { name: "fetch.py" } }
  build {}
}

upload {
  pkg_prefix: "infra/python"
}
