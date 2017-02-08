These are instructions to build the infra/adb/linux-amd64 cipd package, which
is simply the adb binary packaged up.

Choose a build directory. We'll use the enviornment variable `$ROOT` to
represent it.

    $ cd $ROOT

Grab the platform tools zip from the android SDK. Note that this URL points
to the latest version.

    $ curl -o platform_tools.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip
    $ unzip platform_tools.zip && rm platform_tools.zip

Move the binary out of the zip and clear everything else out.

    $ mv platform_tools/adb .
    $ rm -rf platform_tools/

Now $ROOT should contain only the adb binary. Grab its version num.

    $ ./adb version

Should be something like "1.0.36". Now create the CIPD package and deploy
it to the CIPD server. Tag it with the adb version:

```
$ cipd create \
    -name infra/adb/linux-amd64 \
    -in $ROOT \
    -tag "adb_version:<adb_version>"
```
