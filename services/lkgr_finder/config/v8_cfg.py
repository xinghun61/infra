V8_NORMAL_STEPS = ['compile', 'Check', 'Test262', 'Mozilla']

V8_CHECK = ['compile', 'Check']

V8_TEST262 = ['compile', 'Test262']

V8_GC = ['Mjsunit', 'Webkit']

CONFIG = {
  "project": "v8",
  "source_vcs": "svn",
  "source_url": "http://v8.googlecode.com/svn/branches/bleeding_edge",
  "status_url": "https://v8-status.appspot.com",
  "error_recipients": "machenbach@google.com",
  "masters": {
    "client.v8": {
      "base_url": "https://build.chromium.org/p/client.v8",
      "builders": {
        'V8 Linux - builder': ['compile'],
        'V8 Linux - debug builder': ['compile'],
        'V8 Linux - nosnap builder': ['compile'],
        'V8 Linux - nosnap debug builder': ['compile'],
        'V8 Linux': [
          'Check',
          'OptimizeForSize',
          'Test262',
          'Mozilla',
          'Presubmit',
          'Static-Initializers',
          'Webkit',
        ],
        'V8 Linux - debug': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - shared': V8_NORMAL_STEPS,
        'V8 Linux64 - builder': ['compile'],
        'V8 Linux64 - debug builder': ['compile'],
        'V8 Linux64': ['Check', 'OptimizeForSize', 'Test262', 'Mozilla',
                       'Static-Initializers'],
        'V8 Linux64 - debug': ['Check', 'Webkit', 'Test262', 'Mozilla'],
        'V8 Linux64 ASAN': ['Check'],
        # TODO(machenbach): Enable as soon as crbug.com/382930 is resolved.
        # 'V8 Linux - nosnap': ['Check', 'Test262', 'Mozilla'],
        # 'V8 Linux - nosnap - debug': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - isolates': ['Check'],
        'V8 Linux - debug - isolates': ['Check'],
        'V8 Linux - nosse2': ['Check', 'Test262', 'Mozilla', 'GCMole'],
        'V8 Linux - debug - nosse2': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - nosse3': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - debug - nosse3': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - nosse4': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - debug - nosse4': ['Check', 'Test262', 'Mozilla'],
        'V8 Linux - deadcode': ['Check', 'Test262', 'Mozilla'],
        # TODO(machenbach): Disabled until enough slaves are available.
        # 'V8 Linux - interpreted regexp': V8_CHECK,
        'V8 Win32 - builder': ['compile'],
        'V8 Win32 - 1': ['Check', 'Test262', 'Mozilla', 'Webkit'],
        'V8 Win32 - 2': ['Check', 'Test262', 'Mozilla', 'Webkit'],
        'V8 Win32 - debug builder': ['compile'],
        'V8 Win32 - debug - 1': ['Check', 'Webkit', 'Test262', 'Mozilla'],
        'V8 Win32 - debug - 2': ['Check', 'Webkit', 'Test262', 'Mozilla'],
        'V8 Win32 - debug - 3': ['Check', 'Webkit', 'Test262', 'Mozilla'],
        'V8 Win64': V8_NORMAL_STEPS,
        'V8 Mac': V8_NORMAL_STEPS + ['Webkit'],
        'V8 Mac - debug': V8_CHECK + ['Webkit', 'Test262', 'Mozilla'],
        'V8 Mac64': V8_NORMAL_STEPS + ['Webkit'],
        'V8 Mac64 - debug': V8_CHECK + ['Webkit', 'Test262', 'Mozilla'],
        'V8 Arm - builder': ['compile'],
        'V8 Arm': V8_CHECK + ['OptimizeForSize', 'Webkit'],
        'V8 Arm - debug': V8_CHECK + ['OptimizeForSize', 'Webkit'],
        'V8 Linux - arm - sim': V8_CHECK + ['Test262', 'Mozilla'],
        'V8 Linux - arm - sim - debug': V8_CHECK + ['Test262', 'Mozilla'],
        'V8 Linux - arm64 - sim': V8_CHECK + ['Webkit', 'Test262', 'Mozilla'],
        'V8 Linux - arm64 - sim - debug': (V8_CHECK +
                                           ['Webkit', 'Test262', 'Mozilla']),
        'V8 GC Stress - 1': V8_GC,
        'V8 GC Stress - 2': V8_GC,
        'V8 GC Stress - 3': V8_GC,
        'Linux Debug Builder': ['compile'],
        'Linux ASAN Builder': ['compile'],
        'Android Builder': ['compile'],
        'V8 Linux GN': ['compile'],
        # TODO(machenbach): Disabled until there are pure builders available for
        # this. With a perf BuilderTester, the total lkgr cycle time is too big.
        # 'Chrome Win7 Perf': ['compile'],
        # 'Chrome Mac10.6 Perf': ['compile'],
        # 'Chrome Linux Perf': ['compile'],
        # TODO(machenbach): Disabled until stability issues with the windows bot
        # are resolved.
        # 'Webkit': ['compile'],
        'Webkit Mac': ['compile'],
        'Webkit Linux': ['compile'],
        'Webkit Linux 64': ['compile'],
        'Webkit Linux - dbg': ['compile'],
      },
    },  # client.v8
  },
}
