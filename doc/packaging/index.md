# Infra packaging instructions.

Software bundled for Infra should strive to be:

1. Independent and self-sufficient, to simplify deployment and upgrade
   procedures.
1. Relocatable, as it may be installed at an arbitrary path.
1. Compatible with other packages.
1. Compatible with other instances of itself on the same system.

Instructions for specially packaging some Infra tooling:

- [git](git.md)
- [python](python.md)
