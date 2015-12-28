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


Example of a cron task:

    {
      "name": "cleanup_logs",
      "root_directory": "/opt/infra-python",
      "tool": "infra.tools.cleanup_logs",
      // alternative: "cmd": "./run.py infra.tools.cleanup_logs",
      "args": []
      // All times are UTC
      "scheduling": [
          "every month offset 2d8h30m",
          "every workday offset 8h30m",
          "every monday every hour offset 30m",
          "every 5m offset 1m"
      ]
      "timeout": "2h"
    }

# Example equivalence with Unix Cron:

    */30 * * * * chrome-bot
    every 30m
    
    * * * * * chrome-bot
    every 1m   # implicitly: @ 0m
    
    0-59/10 0,10-23 * * * chrome-bot
    every 10m every 1d @ 10:00-01:00
    
    0-59/10 1-9 * * * chrome-bot
    every 10m every 1d @ 01:00-10:00
    
    1-59/10 * * * * chrome-bot
    every 10m @ 1m
    
    2-59/10 * * * * chrome-bot
    every 10m @ 2m
    
    15 4 * * * chrome-bot
    every 1d @ 04:15    # shorten to "@ 04:15" ?
    
    0 1 * * *  chrome-bot
    every 1d @ 01:00
    
    00,10,20,30,40,50 * * * * chrome-bot
    every 10m
    every 1h @ 0m, 10m, 20m, 40m, 50m  # alternative
    
    06,16,26,36,46,56 * * * * chrome-bot
    every 10m @ 6m
    
    50 * * * * chrome-bot
    every 1h @ 50m
    
    */5 * * * * chrome-bot
    every 5m
    
    * 1 * * * chrome-bot
    every 1m every 1d @ 01:00-02:00

