create {
  platform_re: "windows-.*"
  unsupported: true
}

create {
  source { patch_version: "chromium.14" }
  verify { test: "python_test.py" }
}

create {
  platform_re: "linux-.*|mac-.*"
  source {
    # Python 2 is officially done, and 2.7.15 is the last official release.
    cipd {
      pkg: "infra/third_party/source/python"
      default_version: "2.7.15",
      original_download_url: "https://www.python.org/downloads/release/python-2715/"
    }
    unpack_archive: true
    patch_dir: "patches"
  }
  build {
    tool: "autoconf"
    tool: "sed"            # Used by python's makefiles
    tool: "pip_bootstrap"
  }
}

create {
  platform_re: "mac-.*"
  build {
    dep: "bzip2"
    dep: "readline"
    dep: "ncurses"
    dep: "zlib"
    dep: "sqlite"
    dep: "openssl"
  }
}

create {
  platform_re: "linux-.*"
  build {
    dep: "bzip2"
    dep: "readline"
    dep: "ncurses"
    dep: "zlib"
    dep: "sqlite"
    dep: "openssl"

    # On Linux, we need to explicitly build libnsl; on other platforms, it is
    # part of 'libc'.
    dep: "nsl"
  }
}

upload { pkg_prefix: "tools" }
