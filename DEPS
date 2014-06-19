deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "depot_tools":
    "https://chromium.googlesource.com/chromium/tools/depot_tools.git",

  # external deps
  "infra/infra/ext/requests":
    ("https://chromium.googlesource.com/infra/third_party/requests.git"
     "@6366d3dd190a9e58ca582955cddf7e2ac5f32dcc"),

  "infra/infra/ext/argcomplete":
    ("https://chromium.googlesource.com/infra/third_party/argcomplete.git"
     "@a88dcaae3132003ae123d39a2cd9924113b8f985"),
}

hooks = [
  {
    "pattern": ".",
    "action": [
      "python", "-u", "infra/run.py",
      "infra.tools.bootstrap.get_appengine", "--dest=..",
    ],
  },
]

recursion = 1
