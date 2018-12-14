# Switch to RotaNG.

This document describes the steps needed to switch over from the cron/python based rotation generator
to the new RotaNG service.

See [Design Doc](https://docs.google.com/document/d/1WdvMckyfzfx9anU1hLHJ16EuvXv4Keo8aUmSTQRuNp4/edit) for further information.


## Switch a rotation to the RotaNG service.

The process to migrate lives at https://rota-ng.appspot.com/switchlist


## FAQ

* The interface looks like something from the early 90s ..

  Yes this was probably the last time I touched HTML so I've had quite a bit of rust to remove off of my frontend skillz.
  This is rapidly getting improved though with the help of the ChOps Frontend team.


* Bugs

  File bugs in [component:Infra>Sheriffing>Rotations](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3ESheriffing%3ERotations). 
