create {
  source { patch_version: "chromium.16" }
  verify { test: "git_test.py" }
}

create {
  platform_re: "linux-.*|mac-.*"

  source { git {
    repo: "https://chromium.googlesource.com/external/github.com/git/git"
    tag_pattern: "v%s"
  }}

  build {
    tool: "autoconf"
    tool: "sed"

    dep: "zlib"
    dep: "curl"
    dep: "pcre2"
  }
}

create {
  platform_re: "windows-.*"
  source { script { name: "windows_fetch.py" }}
  build { install: "build_win.sh" }
}

upload { pkg_prefix: "infra" }
