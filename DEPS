deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "infra/appengine/swarming":
    ("https://chromium.googlesource.com/infra/swarming.git"
     "@fe5c2222c950dd75856cdc1cffea21ab36d482af"),

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

  "infra/appengine/third_party/highlight":
    ("https://chromium.googlesource.com/infra/third_party/highlight.js.git"
     "@fa5bfec38aebd1415a81c9c674d0fde8ee5ef0ba"),

  "infra/appengine/third_party/npm_modules":
    ("https://chromium.googlesource.com/infra/third_party/npm_modules.git"
     "@363892f3b5977a8dcd3d5ea643cdbeb45d79cfc6"),

  "infra/appengine/third_party/pipeline":
    ("https://chromium.googlesource.com/infra/third_party/"
     "appengine-pipeline.git"
     "@e79945156a7a3a48eecb29b792a9b7925631aadf"),

  "infra/appengine/third_party/google-api-python-client":
    ("https://chromium.googlesource.com/external/github.com/google/"
     "google-api-python-client.git"
     "@49d45a6c3318b75e551c3022020f46c78655f365"),

  "infra/appengine/third_party/trace-viewer":
    ("https://chromium.googlesource.com/external/"
     "trace-viewer.git"
     '@' + '76a4496033c164d8be9ee8c57f702b0859cb1911'),

  ## For ease of development. These are pulled in as wheels for run.py/test.py
  "expect_tests":
    "https://chromium.googlesource.com/infra/testing/expect_tests.git",
  "testing_support":
    "https://chromium.googlesource.com/infra/testing/testing_support.git",

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
