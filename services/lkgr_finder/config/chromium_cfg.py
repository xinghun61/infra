CONFIG = {
  "project": "chromium",
  "source_vcs": "svn",
  "source_url": "svn://svn.chromium.org/chrome/trunk/src",
  "masters": {
    "chromium.win": {
      "base_url": "https://build.chromium.org/p/chromium.win",
      "builders": {
        'Win Builder (dbg)': [
          'compile',
        ],
        'Win7 Tests (dbg)(1)': [
          'ash_unittests',
          'aura_unittests',
          'base_unittests',
          'cacheinvalidation_unittests',
          'cc_unittests',
          'check_deps',
          'chromedriver_unittests',
          'components_unittests',
          'compositor_unittests',
          'content_unittests',
          'courgette_unittests',
          'crypto_unittests',
          'installer_util_unittests',
          'ipc_tests',
          'jingle_unittests',
          'media_unittests',
          'ppapi_unittests',
          'printing_unittests',
          'remoting_unittests',
          'sql_unittests',
          'sync_unit_tests',
          'ui_unittests',
          'unit_tests',
          'url_unittests',
          'views_unittests',
          'webkit_compositor_bindings_unittests',
        ],
        'Win7 Tests (dbg)(2)': [
          'net_unittests', 'browser_tests',
        ],
        'Win7 Tests (dbg)(3)': [
          'browser_tests',
        ],
        'Win7 Tests (dbg)(4)': [
          'browser_tests',
        ],
        'Win7 Tests (dbg)(5)': [
          'browser_tests',
        ],
        'Win7 Tests (dbg)(6)': [
          'browser_tests',
        ],
      },
    },  # chromium.win
    "chromium.mac": {
      "base_url": "https://build.chromium.org/p/chromium.mac",
      "builders": {
        'Mac Builder (dbg)': [
          'compile',
        ],
        'Mac 10.6 Tests (dbg)(1)': [
          'browser_tests',
          'cc_unittests',
          'chromedriver_unittests',
          'jingle_unittests',
          'ppapi_unittests',
          'printing_unittests',
          'remoting_unittests',
          'url_unittests',
          'webkit_compositor_bindings_unittests',
        ],
        'Mac 10.6 Tests (dbg)(2)': [
          'browser_tests',
          'media_unittests',
          'net_unittests',
        ],
        'Mac 10.6 Tests (dbg)(3)': [
          'base_unittests', 'browser_tests', 'interactive_ui_tests',
        ],
        'Mac 10.6 Tests (dbg)(4)': [
          'browser_tests',
          'components_unittests',
          'content_unittests',
          'ipc_tests',
          'sql_unittests',
          'sync_unit_tests',
          'ui_unittests',
          'unit_tests',
        ],
        'iOS Device': [
          'compile',
        ],
        'iOS Simulator (dbg)': [
          'compile',
          'base_unittests',
          'content_unittests',
          'crypto_unittests',
          'net_unittests',
          'sql_unittests',
          'sync_unit_tests',
          'ui_unittests',
          'url_unittests',
        ],
      },
    },  # chromium.mac
    "chromium.linux": {
      "base_url": "https://build.chromium.org/p/chromium.linux",
      "builders": {
        'Linux Builder (dbg)': [
          'compile',
        ],
        'Linux Builder (dbg)(32)': [
          'compile',
        ],
        'Linux Builder': [
          'checkdeps',
        ],
        'Linux Tests (dbg)(1)(32)': [
          'browser_tests',
          'content_browsertests',
          'net_unittests',
        ],
        'Linux Tests (dbg)(2)(32)': [
          'base_unittests',
          'cacheinvalidation_unittests',
          'cc_unittests',
          'chromedriver_unittests',
          'components_unittests',
          'content_unittests',
          'crypto_unittests',
          'dbus_unittests',
          'device_unittests',
          'gpu_unittests',
          'interactive_ui_tests',
          'ipc_tests',
          'jingle_unittests',
          'media_unittests',
          'nacl_integration',
          'nacl_loader_unittests',
          'ppapi_unittests',
          'printing_unittests',
          'remoting_unittests',
          'sandbox_linux_unittests',
          'sql_unittests',
          'sync_unit_tests',
          'ui_unittests',
          'unit_tests',
          'url_unittests',
          'webkit_compositor_bindings_unittests',
        ],
        'Linux Tests (dbg)(1)': [
          'browser_tests',
          'net_unittests',
        ],
        'Linux Tests (dbg)(2)': [
          'base_unittests',
          'cacheinvalidation_unittests',
          'cc_unittests',
          'chromedriver_unittests',
          'components_unittests',
          'content_unittests',
          'interactive_ui_tests',
          'ipc_tests',
          'jingle_unittests',
          'media_unittests',
          'nacl_integration',
          'nacl_loader_unittests',
          'ppapi_unittests',
          'printing_unittests',
          'remoting_unittests',
          'sandbox_linux_unittests',
          'sql_unittests',
          'sync_unit_tests',
          'ui_unittests',
          'unit_tests',
          'url_unittests',
          'webkit_compositor_bindings_unittests',
        ],
        'Android Builder (dbg)': [
          'slave_steps',
        ],
        'Android Tests (dbg)': [
          'slave_steps',
        ],
        'Android Builder': [
          'slave_steps',
        ],
        'Android Tests': [
          'slave_steps',
        ],
        'Android Clang Builder (dbg)': [
          'slave_steps',
        ],
      },
    },  # chromium.linux
    'chromium.chrome': {
      "base_url": "https://build.chromium.org/p/chromium.chrome",
      "builders": {
        'Google Chrome Linux x64': [  # cycle time is ~14 mins as of 5/5/2012
          'compile',
        ],
      },
    },  # chromium.chrome
  },
}
