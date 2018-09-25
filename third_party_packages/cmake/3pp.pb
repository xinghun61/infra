create {
  platform_re: ".*-386"
  unsupported: true
}

create {
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/Kitware/CMake"
      tag_pattern: "v%s"
    }
    patch_dir: "patches"
  }

  build {
    tool: "cmake@3.11.4"
    tool: "ninja"
  }
}

create {
  # Prebuild cmake@3.11.4 doesn't work on the dockerbuild container for
  # linux-amd64, because of not-very-interesting reasons.
  platform_re: "linux-amd64"
  build {
    tool: ""  # don't need any tools, is self bootstrapping
    install: "install_native.sh"
  }
}

upload { pkg_prefix: "infra" }
