deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "infra/appengine/swarming":
    ("https://chromium.googlesource.com/infra/swarming.git"
     "@f57a688286b552c87b9d92603c26b69b3c55e8b0"),

  # Appengine third_party DEPS
  "infra/appengine/third_party/bootstrap":
    ("https://chromium.googlesource.com/infra/third_party/bootstrap.git"
     "@b4895a0d6dc493f17fe9092db4debe44182d42ac"),

  "infra/appengine/third_party/cloudstorage":
    ("https://chromium.googlesource.com/infra/third_party/cloudstorage.git"
     "@ad74316d12e198e0c7352bd666bbc2ec7938bd65"),

  "infra/appengine/third_party/endpoints-proto-datastore":
    ("https://chromium.googlesource.com/infra/third_party/"
     "endpoints-proto-datastore.git"
     "@971bca8e31a4ab0ec78b823add5a47394d78965a"),

  "infra/appengine/third_party/pipeline":
    ("https://chromium.googlesource.com/infra/third_party/"
     "appengine-pipeline.git"
     "@aebc176319885bb7b6372229999b893947248694"),

  ## external deps
  # v1.11.6
  "infra/bootstrap/virtualenv":
    ("https://github.com/pypa/virtualenv.git"
     "@93cfa83481a1cb934eb14c946d33aef94c21bcb0"),

  "infra/appengine/third_party/src/github.com/golang/oauth2":
  ("https://github.com/golang/oauth2.git"
   "@cb029f4c1f58850787981eefaf9d9bf547c1a722"),
}

hooks = [
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/remove_orphaned_pycs.py",
    ],
  },
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/bootstrap.py",
      "--deps_file", "infra/bootstrap/deps.pyl", "infra/ENV"
    ],
  },
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/get_appengine.py", "--dest=.",
    ],
    # extract in google_appengine/
  },
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/get_appengine.py", "--dest=.",
      "--go",
    ],
    # extract in go_appengine/
  },
]

recursedeps = ['build']
