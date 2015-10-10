vars = {
  # npm_modules.git is special: we can't check it out on Windows because paths
  # there are too long for Windows. Instead we use 'deps_os' gclient feature to
  # checkout it out only on Linux and Mac.
  "npm_modules_revision": "2c5e24a5e2b6b7ddd8c1e49fe732c72da1fdcb3c",
}

deps = {
  "build":
    "https://chromium.googlesource.com/chromium/tools/build.git",

  "infra/luci":
   ("https://chromium.googlesource.com/external/github.com/luci/luci-py"
     "@d03653b1439f6319b1a37cc9a46adfc2783d7c12"),

  "infra/recipes-py":
   ("https://chromium.googlesource.com/external/github.com/luci/recipes-py"
     "@origin/master"),

  "infra/go/src/github.com/luci/luci-go":
    ("https://chromium.googlesource.com/external/github.com/luci/luci-go"
     "@395d7e9e1ae64d3d1e3ed4200d5c13821d9aa1aa"),

  "infra/go/src/github.com/luci/gae":
    ("https://github.com/luci/gae.git"
     "@84d674199367bc12a173d8b9a3483345dc942fdc"),

  # Appengine third_party DEPS
  "infra/appengine/third_party/bootstrap":
    ("https://chromium.googlesource.com/infra/third_party/bootstrap.git"
     "@b4895a0d6dc493f17fe9092db4debe44182d42ac"),

  "infra/appengine/third_party/cloudstorage":
    ("https://chromium.googlesource.com/infra/third_party/cloudstorage.git"
     "@ad74316d12e198e0c7352bd666bbc2ec7938bd65"),

  "infra/appengine/third_party/six":
    ("https://chromium.googlesource.com/infra/third_party/six.git"
     "@e0898d97d5951af01ba56e86acaa7530762155c8"),

  "infra/appengine/third_party/oauth2client":
    ("https://chromium.googlesource.com/infra/third_party/oauth2client.git"
     "@e8b1e794d28f2117dd3e2b8feeb506b4c199c533"),

  "infra/appengine/third_party/uritemplate":
    ("https://chromium.googlesource.com/external/github.com/uri-templates/"
     "uritemplate-py.git"
     "@1e780a49412cdbb273e9421974cb91845c124f3f"),

  "infra/appengine/third_party/httplib2":
    ("https://chromium.googlesource.com/infra/third_party/httplib2.git"
     "@058a1f9448d5c27c23772796f83a596caf9188e6"),

  "infra/appengine/third_party/endpoints-proto-datastore":
    ("https://chromium.googlesource.com/infra/third_party/"
     "endpoints-proto-datastore.git"
     "@971bca8e31a4ab0ec78b823add5a47394d78965a"),

  "infra/appengine/third_party/highlight":
    ("https://chromium.googlesource.com/infra/third_party/highlight.js.git"
     "@fa5bfec38aebd1415a81c9c674d0fde8ee5ef0ba"),

  "infra/appengine/third_party/difflibjs":
    ("https://chromium.googlesource.com/external/github.com/qiao/difflib.js.git"
     "@e11553ba3e303e2db206d04c95f8e51c5692ca28"),

  "infra/appengine/third_party/pipeline":
    ("https://chromium.googlesource.com/external/github.com/"
     "GoogleCloudPlatform/appengine-pipelines.git"
     "@58cf59907f67db359fe626ee06b6d3ac448c9e15"),

  "infra/appengine/third_party/google-api-python-client":
    ("https://chromium.googlesource.com/external/github.com/google/"
     "google-api-python-client.git"
     "@49d45a6c3318b75e551c3022020f46c78655f365"),

  "infra/appengine/third_party/catapult":
    ("https://chromium.googlesource.com/external/github.com/catapult-project/"
     "catapult.git"
     "@b1ed0c91a981cbef63d1e8929914c30532686bf3"),

  "infra/appengine/third_party/gae-pytz":
    ("https://chromium.googlesource.com/external/code.google.com/p/gae-pytz/"
     "@4d72fd095c91f874aaafb892859acbe3f927b3cd"),

  ## For ease of development. These are pulled in as wheels for run.py/test.py
  "expect_tests":
    "https://chromium.googlesource.com/infra/testing/expect_tests.git",
  "testing_support":
    "https://chromium.googlesource.com/infra/testing/testing_support.git",

  # v12.0
  "infra/bootstrap/virtualenv":
    ("https://chromium.googlesource.com/infra/third_party/virtualenv.git"
     "@4243b272823228dde5d18a7400c404ce52fb4cea"),

  "infra/appengine/third_party/src/github.com/golang/oauth2":
  ("https://chromium.googlesource.com/external/github.com/golang/oauth2.git"
   "@cb029f4c1f58850787981eefaf9d9bf547c1a722"),
}


deps_os = {
  "unix": {
    "infra/appengine/third_party/npm_modules":
      ("https://chromium.googlesource.com/infra/third_party/npm_modules.git@" +
      Var("npm_modules_revision")),
  },
  "mac": {
    "infra/appengine/third_party/npm_modules":
      ("https://chromium.googlesource.com/infra/third_party/npm_modules.git@" +
      Var("npm_modules_revision")),
  }
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
  {
    "pattern": ".",
    "action": [
      "python", "-u", "./infra/bootstrap/install_cipd_packages.py", "-v",
    ],
  },
  {
    "pattern": ".",
    "action": [
      "download_from_google_storage",
      "--bucket", "chromium-infra",
      "--recursive",
      "--directory",
      "infra/appengine/milo"
    ]
  }
]

recursedeps = ['build']
