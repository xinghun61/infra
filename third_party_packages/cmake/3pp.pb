create {
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/Kitware/CMake"
      tag_pattern: "v%s"
      patch_dir: "patches"
    }
  }

  build {
    tool: "cmake@3.11.4"
    tool: "ninja"
  }
}

upload { pkg_prefix: "infra" }
