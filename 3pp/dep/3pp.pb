create {
  # dep currently vendors in an old copy of BoltDB which doesn't compile on
  # mips. That said, there will probably be the fancy new `official` dependency
  # management solution before someone needs this package for mips.
  platform_re: ".*-mips.*"
  unsupported: true
}

create {
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/golang/dep"
      tag_pattern: "v%s"
    }

    subdir: "src/github.com/golang/dep"
  }

  build { tool: "go" }
}

upload { pkg_prefix: "go/github.com/golang" }
