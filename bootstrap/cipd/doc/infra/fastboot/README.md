These are instructions to build the infra/fastboot/linux-amd64 cipd package, which
is simply the fastboot binary packaged up.

Choose a build directory. We'll use the environment variable `$ROOT` to
represent it.

    $ cd $ROOT

Grab the platform tools zip from the android SDK. Note that this URL points
to the latest version.

    $ curl -o platform_tools.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip
    $ unzip platform_tools.zip && rm platform_tools.zip

Move the binary out of the zip and clear everything else out.

    $ mv platform_tools/fastboot .
    $ rm -rf platform_tools/

Now $ROOT should contain only the fastboot binary. Grab its version num.

    $ ./fastboot --version

Should be something like "5943271ace17". Now create the CIPD package and deploy
it to the CIPD server. Tag it with the fastboot version:

```
$ cipd create \
    -name infra/fastboot/linux-amd64 \
    -in $ROOT \
    -tag "fastboot_version:<fastboot_version>"
```
