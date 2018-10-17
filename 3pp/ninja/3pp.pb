create {
  platform_re: ".*-386"
  unsupported: true
}

create {
  source { git {
    repo: "https://chromium.googlesource.com/external/github.com/ninja-build/ninja"
    tag_pattern: "v%s"
  }}
  build {
    tool: "ninja"  # Depend on the bootstrapped version when cross-compiling
    tool: "re2c"
  }
}

create {
  platform_re: "windows-.*|mac-.*|linux-amd64"
  build {
    tool: "re2c"
    install: "install_bootstrap.sh"
  }
}

upload { pkg_prefix: "tools" }
