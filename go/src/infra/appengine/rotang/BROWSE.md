# Organization of the code.

This document describes the structure of the RotaNG code.


## Basic structure.

```
.
├── cmd
│   ├── app
│   │   ├── app.go
│   │   ├── app.infra_testing
│   │   ├── app_local.yaml
│   │   ├── app_prod.yaml
│   │   ├── app_staging.yaml
│   │   ├── css
│   │   ├── images
│   │   ├── static
│   │   ├── templates
│   └── handlers
├── Makefile
├── OWNERS
├── pkg
│   ├── algo
│   ├── calendar
│   ├── datastore
│   └── jsoncfg
├── README.md
├── rotang.go

16 directories, 81 files
```

* *cmd*; Contains the application(s).
  * *app*; The Appengine application **app.go** and its configuration **app_*\**.yaml** lives here.
    * `app_local.yaml`, `app_staging.yaml` and `app_prod.yaml` contains configurations for respective environment.
    * The `static` folder contains the JS elements used by the rota service.
    * The `templates` folder contains html templates used by the handlers to generate the Web UI pages.
  * *handlers*; Contains all the HTTP handlers.
    * `handler_.*.go` <- HTTP handlers used for external requests to the service.
    * `job_.*.go` <- Appengine cron handlers. Recurring jobs.

  The cmd folder should contain application code, something using the packages in the **pkg** folder.

* *pkg*; Contains the Go packages used by this project.
  * *datastore*; Implements the storer interfaces using Appengine datastore.
  * *jsoncfg*; handles the conversion from the legacy JSON configuration to the ones used by this service.
  * algo: This folder contains the generators used to generate new rotation shifts.
  * calendar: Implements the Caledrer interface using Google calendar.

  The pkg folder should contain Go packages used by the applications. A package should not depend on any other
  package in this folder. They should only implement/use interfaces/types defined in the main *rotang.go* package.

* *rotang.go*; This is the root file containing the domain specific types and interfaces used by this service.

  This package should not import any packages inside this project and contain little to no logic.
