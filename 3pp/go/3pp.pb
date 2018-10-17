create {
  source {
    script {
      name: "fetch.py"
      name: "prebuilt"
    }
    unpack_archive: true
    no_archive_prune: true
  }
  build {
    install: "install_official.sh"
  }
}

create {
  platform_re: "linux-mips.*"
  source {
    script {
      name: "fetch.py"
      name: "source"
    }
  }
  build {
    install: "install_source.sh"
    tool: "go"  # depend on the prebuilt version in $PATH
  }
}

upload { pkg_prefix: "tools" }
