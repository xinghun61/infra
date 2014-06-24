CONFIG = {
    'project': 'chromium',
    'source_vcs': 'svn',
    'source_url': 'svn://svn.chromium.org/chrome/trunk/src',
    'masters': {
        'chromium.win': {
            'base_url': 'https://build.chromium.org/p/chromium.win',
            'builders': {
                'Win Builder (dbg)',
                'Win7 Tests (dbg)(1)',
                'Win7 Tests (dbg)(2)',
                'Win7 Tests (dbg)(3)',
                'Win7 Tests (dbg)(4)',
                'Win7 Tests (dbg)(5)',
                'Win7 Tests (dbg)(6)',
            },
        },  # chromium.win
        'chromium.mac': {
            'base_url': 'https://build.chromium.org/p/chromium.mac',
            'builders': {
                'Mac Builder (dbg)',
                'Mac 10.6 Tests (dbg)(1)',
                'Mac 10.6 Tests (dbg)(2)',
                'Mac 10.6 Tests (dbg)(3)',
                'Mac 10.6 Tests (dbg)(4)',
                'iOS Device',
                'iOS Simulator (dbg)',
            },
        },  # chromium.mac
        'chromium.linux': {
            'base_url': 'https://build.chromium.org/p/chromium.linux',
            'builders': {
                'Linux Builder (dbg)',
                'Linux Builder (dbg)(32)',
                'Linux Builder',
                'Linux Tests (dbg)(1)(32)',
                'Linux Tests (dbg)(2)(32)',
                'Linux Tests (dbg)(1)',
                'Linux Tests (dbg)(2)',
                'Android Builder (dbg)',
                'Android Tests (dbg)',
                'Android Builder',
                'Android Tests',
                'Android Clang Builder (dbg)',
            },
        },  # chromium.linux
        'chromium.chrome': {
            'base_url': 'https://build.chromium.org/p/chromium.chrome',
            'builders': {
                # cycle time is ~14 mins as of 5/5/2012
                'Google Chrome Linux x64',
            },
        },  # chromium.chrome
    },
}
