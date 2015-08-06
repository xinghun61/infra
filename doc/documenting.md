# Documenting

Documentation in infra.git should cover these subjects:

* Introductory material, to help newcomers use and contribute to the
  codebase.
* Links to design documents, explaining decisions and overall structure. The
  point of these docs is to give a high-level view of the organisation
  and inner working.

## How to edit these docs

These docs are in
[Markdown](https://gerrit.googlesource.com/gitiles/+/master/Documentation/markdown.md)
and rendered by Gitiles on the fly. To see the source of a file, click "source"
link below any rendered page.

To see the exact preview of your changes, upload your
[CL to Gerrit](contributing.md#gerrit-cls), open it, click `(gitiles)` link
to the right of "Commit", open your file at _that_ revision.

In-depth articles documents are stored in [docs](.) directory. When creating
a new page, remember to add a link to it in the [developers.md](developers.md)
or [users/index.md](users/index.md) file.

## Styleguide

* For headers use `#` and `##` instead of `==` and `--`.
* Titling your links as "link" or "here" tells the reader precisely nothing when
  quickly scanning your doc and is a waste of space. Instead, write the sentence
  naturally, then go back and wrap the most appropriate phrase with the link.
* See more at the [internal Documenting page](http://go/chrome-infra-docs-internal/documenting.md#Styleguide).

## For Googlers

Please see
[internal Documenting page](http://go/chrome-infra-docs-internal/documenting.md).
