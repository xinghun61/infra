# dumpthis

aka *simplified gsutil cp*


Ever wanted to copy a file from the bot to share with others?
`scp` is a good tool, but copying through a bunch of ssh proxies is a pain.
`dumpthis` to the rescue:

    $ ./run.py infra.tools.dumpthis some.log
    Uploading...
    Use https://storage.cloud.google.com/chrome-dumpfiles/click-to-download

You can also stream:

    $ cat haystack.log | grep needle | ./run.py infra.tools.dumpthis


**Bonus** If `depot_tools` in your `$PATH`:

    $ alias yo=cit
    $ tar cz my_broken_checkout | yo dumpthis
