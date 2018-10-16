# CPython 2.7

Differences to typical python installations:
  * Fully statically compiled; no dynamic libraries or dynamic linkage to system
    libraries (except OS X, but we only link to system-guaranteed libraries in
    order to e.g. integrate with Keychain).
  * Includes OpenSSL, sqlite, bzip, gzip, ncurses/readline
  * On linux, ssl is patched to pick up cert bundles from the system-installed
    cert bundle locations. These are:
    * `/etc/ssl`
    * `/usr/lib/ssl`
