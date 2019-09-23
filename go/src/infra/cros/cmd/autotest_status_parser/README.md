# Autotest results parser.

[TOC]

This binary is used by `skylab_swarming_worker` and `skylab_test_runner` to
extract test results from the test result summary file (`status.log`) and the
exit code file (`.autoserv_execute`) created by the autotest harness inside the
results directory. The parsing is a simpler version of the one done by
tko/parse.

## `status.log` format
The `status.log` file consists of test event lines and miscellaneous stderr
output. The test event lines are nested according to the subtest hierarchy.
Each event line
* starts with a number of tab characters represeting the nesting depth,
* consists of strings separated by the tab character,
* has the following format:
```status	testDirectory	testName	key1=value1	key2=value2	...	comments and/or failure reason
```
Status can be "START", "INFO", test result outcome ("GOOD", "FAIL", "WARN" etc)
or "END " + test result outcome ("END GOOD", etc).

The default (undefined) value for `testDirectory` and `testName` is "----".

Each subtest block starts with a "START" event line and ends with an "END ..."
event line.

## A typical `status.log` file
```
START	test1	test1	timestamp=1561420800	localtime=Jun 26 00:00:00
	START	test1_subtest	test1_subtest	timestamp=1561420801	localtime=Jun 26 00:00:01
		START	----	----	timestamp=1561420802	localtime=Jun 26 00:00:02
			GOOD	----	sysinfo.before	timestamp=1561420803	localtime=Jun 26 00:00:03
		END GOOD	----	----	timestamp=1561420804	localtime=Jun 26 00:00:04
		FAIL	test1_subtest	test1_subtest	timestamp=1561420805	localtime=Jun 26 00:00:05	The test failed because reasons.
	END FAIL	test1_subtest	test1_subtest	timestamp=1561420805	localtime=Jun 26 00:00:05
	FAIL	test1	test1	timestamp=1561420806	localtime=Jun 26 00:00:06	test1_subtest failed.
END FAIL	test1	test1	timestamp=1561420806	localtime=Jun 26 00:00:06
START	test2	----	timestamp=1561420800	localtime=Jun 26 00:00:07
	INFO	test2	----	timestamp=1561420805	localtime=Jun 26 00:00:08	This test has no name.
	WARN	test2	----	timestamp=1561420806	localtime=Jun 26 00:00:09	Something suspicious happened.
END WARN	test2	----	timestamp=1561420806	localtime=Jun 26 00:00:09
START	----	test3	timestamp=1561420800	localtime=Jun 26 00:00:10
	INFO	----	test3	timestamp=1561420810	localtime=Jun 26 00:00:10	This test has no directory.
	ERROR	----	test3	timestamp=1561420811	localtime=Jun 26 00:00:11	Unhandled AutoservRunError: command execution error
  * Command:
    ...
  Exit status: 1
  Duration: 0.00010000000

  stderr:
  ...
  [0626/000011.000000:ERROR:update_engine_client.cc(519)] Error checking for update.
  Traceback (most recent call last):
    ...
    File "/usr/local/autotest/server/hosts/ssh_host.py", line 268, in _run
      raise error.AutoservRunError("command execution error", result)
  AutoservRunError: command execution error
END ERROR	----	test3	timestamp=1561420811	localtime=Jun 26 00:00:11
```

## Parsing `status.log`

The goal of this parser is to report a flat list of (sub)test cases together
with a simple pass/fail verdict and comment on what went wrong. In the current
implementation the verdict is obtained from the "END ..." test event lines and
the human readable summary is obtained from "FAIL"/"ERROR"/"WARN"/etc test
event lines. "INFO" and "GOOD" lines are ignored. Initial tab characters are
ignored - the nesting is determined via keeping track of "START" and "END ..."
event lines.
