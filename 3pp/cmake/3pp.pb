create {
  platform_re: ".*-386"
  unsupported: true
}

create {
  platform_re: "linux-.*|mac-.*"
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/Kitware/CMake"
      tag_pattern: "v%s"
    }
    patch_dir: "patches"
  }

  build {
    tool: "cmake_bootstrap"
    tool: "ninja"
  }
}

upload { pkg_prefix: "infra" }
