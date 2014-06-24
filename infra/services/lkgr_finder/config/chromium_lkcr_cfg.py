CONFIG = {
    'project': 'chromium_lkcr',
    'source_vcs': 'svn',
    'source_url': 'svn://svn.chromium.org/chrome/trunk/src',
    'status_url': 'https://build.chromium.org/p/chromium/lkcr-status',
    'masters': {
        'chromium.win': {
            'base_url': 'https://build.chromium.org/p/chromium.win',
            'builders': {
                'Win Builder',
                'Win Builder (dbg)',
                'Win x64 Builder',
                'Win x64 Builder (dbg)',
            },
        },  # chromium.win
        'chromium.mac': {
            'base_url': 'https://build.chromium.org/p/chromium.mac',
            'builders': {
                'Mac Builder',
                'Mac Builder (dbg)',
            },
        },  # chromium.mac
        'chromium.linux': {
            'base_url': 'https://build.chromium.org/p/chromium.linux',
            'builders': {
                'Linux Builder',
                'Linux Builder (dbg)',
                'Linux Builder (dbg)(32)',
                'Linux Clang (dbg)',
                'Android Builder (dbg)',
                'Android Builder',
                'Android Clang Builder (dbg)',
            },
        },  # chromium.linux
    },
}
