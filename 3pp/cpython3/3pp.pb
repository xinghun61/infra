create {
  verify { test: "python_test.py" }
}

create {
  platform_re: "linux-.*|mac-.*"
  source {
    git {
      repo: "https://chromium.googlesource.com/external/github.com/python/cpython"
      tag_pattern: "v%s",
    }
    patch_dir: "patches"
    patch_version: "chromium.1"
  }
  build {
    # no binutils on mac since it includes some tools like 'ar' that we don't
    # actually want
    tool: "autoconf"
    tool: "pip_bootstrap"
    tool: "sed"
  }
}

create {
  platform_re: "mac-.*"
  build {
    dep: "bzip2"
    dep: "libffi"
    dep: "libuuid"
    dep: "ncursesw"
    dep: "openssl"
    dep: "readline"
    dep: "sqlite"
    dep: "xzutils"
    dep: "zlib"
  }
}

create {
  platform_re: "linux-.*"
  build {
    dep: "bzip2"
    dep: "libffi"
    dep: "libuuid"
    dep: "ncursesw"
    dep: "openssl"
    dep: "readline"
    dep: "sqlite"
    dep: "xzutils"
    dep: "zlib"

    # On Linux, we need to explicitly build libnsl; on other platforms, it is
    # part of 'libc'.
    dep: "nsl"

    tool: "binutils"
    tool: "autoconf"
    tool: "pip_bootstrap"
    tool: "sed"
  }
}

create {
  platform_re: "linux-arm.*|linux-mips.*"
  build {
    tool: "autoconf"
    tool: "binutils"
    tool: "pip_bootstrap"
    tool: "sed"            # Used by python's makefiles

    tool: "cpython3"
  }
}

create {
  platform_re: "windows-.*"
  source { script { name: "fetch.py" } }
  build {
    tool: "lessmsi"
    tool: "pip_bootstrap"

    install: "install_win.sh"
  }
  verify { test: "python_test.py" }
}

upload { pkg_prefix: "tools" }
