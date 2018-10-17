create {
  platform_re: "linux-.*|mac-.*"
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/swig/swig"
      tag_pattern: "rel-%s"
    }
    patch_dir: "patches"
  }
  build {
    dep: "pcre"
    tool: "autoconf"
    tool: "automake"
  }
}

upload { pkg_prefix: "tools" }
