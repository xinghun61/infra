deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "depot_tools":
    "https://chromium.googlesource.com/chromium/tools/depot_tools.git",

  ## external deps
  # v1.11.6
  "infra/bootstrap/virtualenv":
    ("https://github.com/pypa/virtualenv.git"
     "@93cfa83481a1cb934eb14c946d33aef94c21bcb0"),
}

hooks = [
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/bootstrap.py", "--deps_file",
      "infra/bootstrap/deps.pyl", "infra/ENV"
    ],
  },
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/get_appengine.py", "--dest=.",
    ],
  },
]

recursion = 1
