CONFIG = {
  "project": "chromium_lkcr",
  "source_vcs": "svn",
  "source_url": "svn://svn.chromium.org/chrome/trunk/src",
  "status_url": "https://build.chromium.org/p/chromium/lkcr-status",
  "masters": {
    "chromium.win": {
      "base_url": "https://build.chromium.org/p/chromium.win",
      "builders": {
        'Win Builder': [
          'compile',
          'runhooks',
          'update',
        ],
        'Win Builder (dbg)': [
          'compile',
          'runhooks',
          'update',
        ],
        'Win x64 Builder': [
          'compile',
          'runhooks',
          'update',
        ],
        'Win x64 Builder (dbg)': [
          'compile',
          'runhooks',
          'update',
        ],
      },
    },  # chromium.win
    "chromium.mac": {
      "base_url": "https://build.chromium.org/p/chromium.mac",
      "builders": {
        'Mac Builder': [
          'bot_update,'
          'compile',
          'gclient runhooks',
        ],
        'Mac Builder (dbg)': [
          'bot_update,'
          'compile',
          'gclient runhooks',
        ],
      },
    },  # chromium.mac
    "chromium.linux": {
      "base_url": "https://build.chromium.org/p/chromium.linux",
      "builders": {
        'Linux Builder': [
          'compile',
          'gclient runhooks',
        ],
        'Linux Builder (dbg)': [
          'compile',
          'gclient runhooks',
        ],
        'Linux Builder (dbg)(32)': [
          'compile',
          'gclient runhooks',
        ],
        'Linux Clang (dbg)': [
          'bot_update',
          'compile',
          'gclient runhooks',
        ],
        'Android Builder (dbg)': [
          'compile',
          'runhooks',
          'update',
        ],
        'Android Builder': [
          'compile',
          'runhooks',
          'update',
        ],
        'Android Clang Builder (dbg)': [
          'compile',
          'runhooks',
          'update',
        ],
      },
    },  # chromium.linux
  },
}
