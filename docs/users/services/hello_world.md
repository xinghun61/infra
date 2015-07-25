# Hello World service

Can generate a greeting string in different tones and languages.

*   Locations
    *   Prod instance: [helloworld.appspot.com](http://helloworld.appspot.com)
    *   Test instance: [helloworld-test.appspot.com](http://helloworld.appspot.com)
    *   Example: [greetings of new chromium committers](http://helloworld.appspot.com/chromium)
*   [Documentation]([/appengine/helloworld/README.md])
*   [Design Doc](https://docs.google.com/document/d/lalalaJxY7jzFcgs1OCHcniQ/edit#)
*   [API](http://helloworld.appspot.com/_ah/api/explorer)
*   Safe to use for internal projects: yes, has ACLs.
*   Has SLA: no.
*   Crbug label: [Infra-HelloWorld](https://code.google.com/p/chromium/issues/list?q=Infra%3DHelloWorld)
*   Owner: johndoe@chromium.org

## Configuration

[Register your project](luci_config.md#Register), add `hello_world.cfg` config
file to `infra/config` branch of your repo. The file format is described by
`HelloWorldCfg` message in
[hello_world.proto](http://link.to.documented.proto.file).

Example:
[`hello_world.cfg` in Chromium project](http://chromium.googlesource.com/chromium/src/+/infra/config/hello_world.cfg).

## Security

Hello World service is safe to use for internal projects.
It uses [standard "access" project metadata field](project_registry.md#access).

## Limitations

* Supports only English, Chinese, Spanish and Russian.
* Assumes `"FirstName LastName"` format ([BUG](http://crbug/1234)).
