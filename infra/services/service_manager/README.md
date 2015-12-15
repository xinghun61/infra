# Service Manager

The `service_manager` starts, monitors and stops long-running processes on the
machine.  Any tool runnable by `infra/run.py` can be made into a service
controlled by `service_manager`.

Services are configured with JSON config files in `/etc/infra-services`.

Each config file defines one service.  A service will be started immediately
when its config file is added to that directory, will be stopped when the config
is removed, and will be restarted when the config is changed.

The config file contains a JSON object with the following fields:

* __name__       - A short friendly name for the service.
* __root_directory__  - The directory that contains `run.py`.
* __tool__      - The python module containing `__main__.py`, such as
                   'infra.services.sysmon'.  You can run `./run.py` by itself
                   with 
                   no arguments to see a list of these.
* __args__       - (optional, default []) A list of commandline arguments to
                   pass to the tool.
* __stop\_time__  - (optional, default 10 seconds) Number of seconds to give the
                   service to shut itself down after receiving a SIGTERM.
                   `service_manager` will send a SIGKILL after this time if the
                   service is still running.

Example:

    {
      "name": "mastermon",
      "root_directory": "/opt/infra-python",
      "tool": "infra.services.mastermon",
      "args": [
        "--url", "http://build.chromium.org/p/chromium",
        "--ts-mon-endpoint", "file:///tmp/metrics"
      ],
      "stop_time": 5
    }
