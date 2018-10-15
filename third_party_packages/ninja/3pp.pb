create {
  platform_re: ".*-386"
  unsupported: true
}

create {
  source { git {
    repo: "https://chromium.googlesource.com/external/github.com/ninja-build/ninja"
    tag_pattern: "v%s"
  }}
  build {}
}

upload { pkg_prefix: "infra" }
