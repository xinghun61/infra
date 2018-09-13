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

upload { pkg_prefix: "go/cmd/github.com/golang/dep" }
