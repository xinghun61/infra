# VPython and You ([go/vpython-and-you])
## How Chromium Infrastructure handles Python package distribution.
Authors/Contacts: iannucci@, nodir@, dnj@

### What is VPython?
[VPython] is a tool created by Chrome Ops to run Python scripts in [Python
VirtualEnvs]. VirtualEnvs are a way to have each script use an isolated set of
Python packages (e.g. stuff from [PyPI]). E.g. if one script needs requests v1.2
and another needs v2.0, they can both execute on the same system without issues.
Using VPython ensures that all Python that is run on Infra systems uses isolated
and reproducible environments.

VPython searches for “[vpython spec]” files (example) to tell it what packages
it should load into the VirtualEnv. No spec file means an ‘empty’ VirtualEnv,
which looks like a fresh installation of Python without any extra packages.

### When should I use VPython?
Think of VPython as creating a “bubble” around your script, removing
environmental influences; you only want your ‘friend’ scripts in the same
bubble. Scripts you don’t control in tandem with the caller script should have
their own bubbles.

For example, a ‘wrapper’ script that sets up some non-python environment
(daemon, credentials) and then invokes a target script should use ‘vpython’.
This will allow the target script to have its own package deps (expressed in
a “vpython spec”) and not accidentally inherit any of the deps belonging to the
wrapper.

OTOH, a ‘launcher’ script that tweaks PYTHONPATH and then calls a subscript
should NOT use vpython, because vpython would make a new “bubble” around it,
deleting all changes to PYTHONPATH. In this case, the launcher and subscript are
“in the same bubble”.

### How can I use VPython?
`vpython` (and `vpython.bat` on windows) are already in $PATH via [buildbot],
[LUCI], and [depot_tools]. After adding any “vpython spec”s that your script
needs to the repo containing your script, use `vpython` exactly the way that you
would have used `python` to invoke the script. So instead of `python script.py
arg arg`, call `vpython script.py arg arg`. Recipes can also use vpython by
setting `venv=True` when using the `python` recipe_module.

### What if I need a new VPython wheel?
First check to see if the wheel is already available in [wheels.md]. If not,
file a bug [here](https://bugs.chromium.org/p/chromium/issues/entry?summary=Need%20VPython%20Wheel&description=Link%20to%20PyPI:%20%0AWheel%20Name:%20%0AVersion:%20%0APlatform(s)%20Required:%20%0A%0A%0ANote%20to%20Foundation%20Trooper:%0AFollow%20https://chromium.googlesource.com/infra/infra/+/master/infra/tools/dockerbuild/README.wheels.md&components=Infra>Platform>Admin).

[go/vpython-and-you]: ./vpython_one_page.md
[VPython]: ./vpython.md
[Python VirtualEnvs]: https://virtualenv.pypa.io/en/stable/
[PyPI]: https://pypi.python.org/
[vpython spec]: https://chromium.googlesource.com/chromium/src.git/+/master/.vpython
[buildbot]: https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/cipd_bootstrap_v2.py#43
[LUCI]: https://chrome-internal.googlesource.com/infradata/config/+/master/configs/cr-buildbucket/swarming_task_template.json#70
[depot_tools]: https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/cipd_manifest.txt#11
[wheels.md]: https://chromium.googlesource.com/infra/infra/+/master/infra/tools/dockerbuild/wheels.md
