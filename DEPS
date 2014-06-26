deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "depot_tools":
    "https://chromium.googlesource.com/chromium/tools/depot_tools.git",

  ## external deps
  # v0.8.0
  "infra/infra/ext/argcomplete":
    ("https://chromium.googlesource.com/infra/third_party/argcomplete.git"
     "@a88dcaae3132003ae123d39a2cd9924113b8f985"),

  # v1.5 (v2 requires more dependencies)
  "infra/infra/ext/dateutil":
    ("https://chromium.googlesource.com/infra/third_party/dateutil.git"
     "@731ee1ce8456361eba2c619e90989f6db45625b9"),

  # master at 2014-05-03 9:27-4
  "infra/infra/ext/httplib2":
    ("https://chromium.googlesource.com/infra/third_party/httplib2.git"
     "@7d1b88a3cf34774242bf4c0578c09c0092bb05d8"),

  # master at 2014-06-25 15:56-7
  "infra/infra/ext/oauth2client":
    ("https://chromium.googlesource.com/infra/third_party/oauth2client.git"
     "@1a3a99f11369806d7c517350df0b95ec50c317dd"),

  # master at 2014-06-02 12:44+0
  "infra/infra/ext/pytz":
    ("https://chromium.googlesource.com/infra/third_party/pytz.git"
     "@056207cdda4a8f01f7f0bd924e89d0df434c7547"),

  # v2.3.0
  "infra/infra/ext/requests":
    ("https://chromium.googlesource.com/infra/third_party/requests.git"
     "@6366d3dd190a9e58ca582955cddf7e2ac5f32dcc"),
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
