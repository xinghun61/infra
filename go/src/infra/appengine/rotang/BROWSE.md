# Organization of the code.

This document describes the structure of the RotaNG code.


## Basic structure.

```
    rotang
    ├── cmd
    │   ├── app
    │   │   ├── app.go
    │   │   ├── app.yaml
    │   │   ├── css
    │   │   ├── images
    │   │   └── token
    │   └── handlers
    │       ├── handle_index.go
    │       ├── handle_index_test.go
    │       ├── handlers.infra_testing
    │       ├── handle_upload.go
    │       ├── handle_upload_test.go
    │       ├── ...
    │       └── templates
    │           └── pages
    │               ├── index.html
    │               └── upload.html
    │               └── ...
    ├── pkg
    │   ├── datastore
    │   │   ├── datastore.go
    │   │   └── datastore_test.go
    │   └── jsoncfg
    │       ├── jsoncfg.go
    │       └── jsoncfg_test.go
    ├── Makefile
    ├── OWNERS
    ├── README.md
    └── rotang.go
```

* *cmd*; Contains the application(s).
  * *app*; The Appengine application **app.go** and its configuration **app.yaml** lives here.
  * *handlers*; Contains all the HTTP handlers.
  * rotang-tool; The CLI tool.

  The cmd folder should contain application code, something using the packages in the **pkg** folder.

* *pkg*; Contains the Go packages used by this project.
  * *datastore*; Implements the storer interfaces using Appengine datastore.
  * *jsoncfg*; handles the conversion from the legacy JSON configuration to the ones used by this service.

  The pkg folder should contain Go packages used by the applications. A package should not depend on any other
  package in this folder. They should only implement/use interfaces/types defined in the main *rotang.go* package.

* *rotang.go*; This is the root file containing the domain specific types and interfaces used by this service.

  This package should not import any packages inside this project and contain little to no logic.
