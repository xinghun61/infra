CONFIG = {
  "project": "blink",
  "source_vcs": "svn",
  "source_url": "svn://svn.chromium.org/chrome/trunk/src",
  "status_url": "https://blink-status.appspot.com",
  "masters": {
    "chromium.win": {
      "base_url": "https://build.chromium.org/p/chromium.win",
      "builders": {
        'Win Builder (dbg)': ['compile'],
      },
    },  # chromium.win
    "chromium.mac": {
      "base_url": "https://build.chromium.org/p/chromium.mac",
      "builders": {
        'Mac Builder (dbg)': ['compile'],
      },
    },  # chromium.mac
    "chromium.linux": {
      "base_url": "https://build.chromium.org/p/chromium.linux",
      "builders": {
        'Linux Builder (dbg)': ['compile'],
        'Linux Builder (dbg)(32)': ['compile'],
        'Android Builder (dbg)': ['slave_steps'],
        'Android Builder': ['slave_steps'],
      },
    },  # chromium.linux
    "chromium.webkit": {
      "base_url": "https://build.chromium.org/p/chromium.webkit",
      "builders": {
        'WebKit Win Builder (deps)': ['compile'],
        'WebKit Mac Builder (deps)': ['compile'],
        'WebKit Linux (deps)': ['compile'],
      },
    },  # chromium.webkit
  },
}
