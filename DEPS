deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "depot_tools":
    "https://chromium.googlesource.com/chromium/tools/depot_tools.git",
}

hooks = [
  {
    "pattern": ".",
    "action": [
      "python", "infra/bootstrap/hooks/get_appengine.py", "--dest=.",
    ],
  },
]

recursion = 1
