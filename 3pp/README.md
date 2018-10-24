# 3pp package definitions

This is a collection of "third-party package" definitions.

See the [support_3pp] recipe module docs for the format of package
definitions.

[support_3pp]: /recipes/README.recipes.md#recipe_modules-support_3pp

# Building stuff locally

See [./run_locally.sh]. You can pass `help` as the first argument for the
lowdown.

# CIPD Sources

Some third-party packages distribute their releases via source tarballs or zips.
Sometimes this is done via http or ftp. For reliability and reproducability
reasons, we prefer to mirror the tarballs ourselves and fetch them from CIPD.

To ingest a new tarball/zip:
  * Download the official tarball release from the software site.
    * pick one that is compressed with gzip, bzip2, or is a zip file.
    * If there's no such tarball, consider expanding compression support
      in the `recipe_engine/archive` module.
  * Put the tarball in an empty directory by itself (don't unpack it). The
    name of the archive doesn't matter. Your directory should now look like:

      some/dir/
          pkgname-1.2.3.tar.gz

  * Now run:

      $ PKG_NAME=pkgname
      $ VERSION=1.2.3
      $ cipd create  \
        -in some/dir \
        -name infra/third_party/source/$PKG_NAME \
        -tag version:$VERSION

  * You can now use the source in a 3pp package definition like:

      source {
        cipd {
          pkg: "infra/third_party/source/pkgname"
          default_version: "1.2.3"
          original_download_url: "https://original.source.url.example.com"
        }
        # Lets 3pp recipe know to expect a single tarball/zip
        unpack_archive: true
      }

  * By default the 3pp recipe also expects unpacked archives to unpack their
    actual contents (files) to a subdirectory (in the Unix world this is typical
    for tarballs to have all files under a folder named the same thing as the
    tarball itself). The 3pp recipe will remove these 'single directories' and
    move all contents to the top level directory. To avoid this behavior, see
    the `no_archive_prune` option.
