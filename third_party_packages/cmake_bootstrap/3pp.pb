create {
  platform_re: "linux-amd64|mac-.*"
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/Kitware/CMake"
      tag_pattern: "v%s"
    }
    patch_dir: "patches"
  }

  build {}
}

upload { pkg_prefix: "infra/third_party/build_support" }
