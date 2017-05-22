# Python packaging instructions.

## Mac and Linux
The procedure for packaging Git for Mac and Linux can be found in the
[third_party_packages](/recipes/recipes/third_party_packages.py) recipe.

## Windows

Overview:

- First python is installed using the official Python installer.
- The necessary system dlls are copied into the Python directory.
- Add additional Python packages to the installation.
- Generate the CIPD package.
- Verify the CIPD package.
- Upload the CIPD package.

The following instructions are for the 64-bit Python installation, but can be
trivially transposed to perform a 32-bit Python installation.

### Python Installation

1. Visit https://www.python.org/downloads/windows/, choose "Windows x86-64 MSI
  installer"
  ([link](https://www.python.org/ftp/python/2.7.13/python-2.7.13.amd64.msi)).
1. Install for "All Users"
1. Install to: `C:\infra\bin`.
1. When customizing, deselect ("Entire feature will not be available") the
  following features:

    - Tcl/Tk
    - Documentation
    - Test suite
    - Add python.exe to Path
1. (32-bit) Move `pythoncom27.dll` and `pywintypes27.dll` from `C:\infra\bin` to
  `C:\infra\bin\Lib\site-packages\win32`.

### Add additional packages

Infra Python includes built-in `pywin32` and `psutil` packages.

#### pywin32

1. Download the latest `pywin32` for Python2.7 from its SourceForce site:
  https://sourceforge.net/projects/pywin32/files/pywin32/
    - The latest is currently
    [Build 221](https://sourceforge.net/projects/pywin32/files/pywin32/Build%20221/).

1. Run the installer. It should list your recent Python installation as an
  installation target.
1. Move the DLLs in `C:\infra\bin\Lib\site-packages\pywin32_system32` to
  `C:\infra\bin\Lib\site-packages\win32`.

#### psutil

1. Enter command prompt.
1. Enter the Python installation directory.
1. Run `Scripts\pip.exe install psutil`
1. Confirm that `psutil` exists in your installation's `Lib/site-packages`
  directory.

### Packaging and Cleanup

1. Create a `C:\infra\doc\python` folder for documentation. Move text files in
  `C:\infra\bin` (e.g., LICENSE.txt, NEWS.txt, README.txt) into this directory.
1. Add a new file to `C:\infra\doc\python` containing the following text,
  replacing `HASH` with the latest commit hash from the
  [infra/infra](https://chromium.googlesource.com/infra/infra/+/master)
  repository.

    ```
    This Python installation was created for Chromium by hand. For instructions
    on how to generate this package, see:

    https://chromium.googlesource.com/infra/infra/+/[HASH]/doc/packaging/python.md
    ```
1. Delete compiled Python files. Run the following command in an administrator-
  owned `cmd.exe` shell:

    ```
    del /s c:\infra\bin\*.pyc
    ```
1. Delete files (if they exist) from `C:\infra\bin`:

    - `pywin32-wininst.log`
    - `Removepywin32.exe`
    - `w9xpopen.exe`
    - `Lib\test`
    - `Lib\lib-tk`
    - `Lib\site-packages\PyWin32.chm`

### Generate the CIPD package

Now, we want to generate the Python CIPD package. The package name has the form
`infra/python/cpython/windows-[ARCH]`, where:

- `ARCH` is the current architecture, either `386` or `amd64`.

1. Generate the package by running:

    ```
    cipd pkg-build -name infra/python/cpython/windows-amd64 -in C:\infra -out %USERPROFILE%\python.pkg
    ```

### Verify the CIPD package

Prior to uploading the new CIPD package, it should be verified on a system.
Ideally, it will be verified on a different, clean system to ensure its
completeness. However, failing that, it may be verified on the builder system.


1. If verifying on the builder system, uninstall Python.
1. Create a testing deployment directory under `%USERPROFILE%` and deploy the package:

    ```
    cipd pkg-deploy -root %USERPROFILE%\pytest %USERPROFILE%\python.pkg
    ```
1. Run the deployed Python:

    ```
    %USERPROFILE%\pytest\bin\python.exe
    ```
1. Verify that the following commands work:

    ```
    import pywin
    import psutil
    import win32api
    ```

### Upload the package to CIPD

We need to generate a tag for the Python package. The tag uses the form
`version:[PYVERSION][SUFFIX]`, where:
- `PYVERSION` is the Python version, in this case `2.7.13`.
- `SUFFIX` is the value of `CPYTHON_PACKAGE_VERSION_SUFFIX` from the
  [third_party_packages](/recipes/recipes/third_party_packages.py).

For example, version `version:2.7.13.chromium`.

1. Upload the generated and verified package to CIPD.

    ```
    cipd pkg-register %USERPROFILE%\python.pkg -tag version:2.7.13.chromium
    ```
