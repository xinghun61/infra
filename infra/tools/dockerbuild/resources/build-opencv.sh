# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -x
set -e

# This script builds OpenCV wheels.
#
# To build an OpenCV wheel, we require:
# 1) The OpenCV source code for the version being built.
# 2) A Python package description to construct the actual wheel
#    (using "opencv-python").
# 3) A "numpy" version that is compatible with the OpenCV version. These two
#    must be deployed alongside each other. Ensuring this is left to the user,
#    but we must establish this dependency during build for the build to work.
#
# This script is higly influenced by the "opencv-python" project and its
# documentation. However, since we want to build for an expanded set of
# platforms and for additional versions ("opencv-python" supports OpenCV3+
# only), and want to build without Travis CI, we perform the build here in our
# own script.
#
# To package "opencv-python" source, run:
# $ git clone https://github.com/skvark/opencv-python
# $ git -C opencv-python submodule update --init --recursive
#
# This script is specifically tuned to work on "manylinux" Intel builders. It is
# generic enough to probably work on others with minimal configs. For example,
# to build on a Mac, change:
# - PYTHON_INCLUDE_PATH to point to the "python2.7" path on the build decide
#   (can be scraped from python-config --includes).
# - PYTHON_PACKAGES_PATH to point to the path that contains "libpython...a",
#   although it may not actually have to point to a valid location.
# - Make sure the builder has "cmake" installed. Dockcross images do, but some
#   Mac builders do not.
#
# Arguments:
#   <workdir>
#   <opencv_python_checkout>
#   <opencv_version>
#   <virtualenv_root>
#   <numpy_wheel_path>
WORKDIR=$1; shift
PY_OPENCV_ROOT=$1; shift
OPENCV_VERSION=$1; shift
VENV_PKG_PATH=$1; shift
NUMPY_WHEEL_PATH=$1; shift

# Ensure that our OpenCV source is writable. As a CIPD package clone, it may
# not have writability.
chmod -R u+w "${PY_OPENCV_ROOT}"

# Create a VirutalEnv with our "numpy" wheel installed.
#
# We clear our PYTHONPATH here because it forces a local system path.
export PYTHONPATH=
VENV_ROOT="${WORKDIR}/venv"
(cd "${WORKDIR}" && python "${VENV_PKG_PATH}"/virtualenv.py "${VENV_ROOT}")

# Add that VirtualEnv to our PATH.
source "${VENV_ROOT}/bin/activate"

# Install "numpy" into the VirutalEnv.
python -m pip install "${NUMPY_WHEEL_PATH}"

# To satisfy (1) and (2), we will use a submodule-recursive "opencv-python"
# checkout. To select our OpenCV version, we will explicitly check it out in
# the "opencv-python" vendored directory.
#
# This script is whittled down from "opencv-python"'s
# //travis/build-wheels.sh
PYTHON_VERSION_STRING=$(python -c "\
from platform import python_version; \
print(python_version()) \
")
PYTHON_INCLUDE_PATH="${PYTHONXCPREFIX}/include/python2.7"
PYTHON_PACKAGES_PATH=/usr/cross/lib
PYTHON_NUMPY_INCLUDE_DIRS=$(python -c "\
import os; \
os.environ['DISTUTILS_USE_SDK']='1'; \
import numpy.distutils; \
print(os.pathsep.join(numpy.distutils.misc_util.get_numpy_include_dirs())) \
")
PYTHON_NUMPY_VERSION=$(python -c "\
import numpy; \
print(numpy.version.version)\
")

echo "Python version string: $PYTHON_VERSION_STRING"
echo "Python include path: $PYTHON_INCLUDE_PATH"
echo "Python packages path: $PYTHON_PACKAGES_PATH"
echo "Python numpy incude dirs: $PYTHON_NUMPY_INCLUDE_DIRS"
echo "Python numpy version: $PYTHON_NUMPY_VERSION"

# Begin build
echo "Begin build"
OPENCV_BUILD="${WORKDIR}/opencv"
if [ -d "${OPENCV_BUILD}" ]; then
  rm -rf "${OPENCV_BUILD}"
fi
mkdir -p "${OPENCV_BUILD}"

echo "Checkout OpenCV [${OPENCV_VERSION}]"
(cd "${PY_OPENCV_ROOT}/opencv" && git checkout "${OPENCV_VERSION}")

echo 'Config for Py2'

# Build targets:
# OpenCV 2: "opencv_python"
# OpenCV 3+: "opencv_python2"
PYTHON_DEFINES=""
case "${OPENCV_VERSION}" in
2.*)
  OPENCV_TARGET="opencv_python"
  ;;

3.*)
  OPENCV_TARGET="opencv_python2"
  ;;

*)
  echo "ERROR: Unknown OpenCV version: [${OPENCV_VERSION}]."
  exit 1
esac

# Note that we define both OpenCV2 (PYTHON_) and OpenCV3 (PYTHON2_...) sets of
# variables.
(cd "${PY_OPENCV_ROOT}/opencv"; \
 cmake -H"." -B"${OPENCV_BUILD}" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_opencv_python3=OFF -DBUILD_opencv_java=OFF \
  -DBUILD_SHARED_LIBS=OFF \
  -DWITH_IPP=OFF -DBUILD_DOCS=OFF \
  -DINSTALL_C_EXAMPLES=OFF -DINSTALL_PYTHON_EXAMPLES=OFF -DBUILD_TESTS=OFF \
  -DBUILD_PERF_TESTS=OFF \
  -DBUILD_EXAMPLES=OFF \
  \
  -DPYTHON_FOUND=ON -DPYTHON_FOUND=ON \
  -DPYTHON_EXECUTABLE="${VENV_ROOT}/bin/python" \
  -DPYTHON_VERSION_STRING="$PYTHON_VERSION_STRING" \
  -DPYTHON_INCLUDE_DIR="$PYTHON_INCLUDE_PATH" \
  -DPYTHON_LIBRARY="$PYTHON_PACKAGES_PATH" \
  -DPYTHON_NUMPY_INCLUDE_DIR="$PYTHON_NUMPY_INCLUDE_DIRS" \
  -DPYTHON_NUMPY_VERSION="$PYTHON_NUMPY_VERSION" \
  -DPYTHON2INTERP_FOUND=ON -DPYTHON2LIBS_FOUND=ON \
  \
  -DPYTHON2_EXECUTABLE=python \
  -DPYTHON2_VERSION_STRING="$PYTHON_VERSION_STRING" \
  -DPYTHON2_INCLUDE_PATH="$PYTHON_INCLUDE_PATH" \
  -DPYTHON2_PACKAGES_PATH="$PYTHON_PACKAGES_PATH" \
  -DPYTHON2_NUMPY_INCLUDE_DIRS="$PYTHON_NUMPY_INCLUDE_DIRS" \
  -DPYTHON2_NUMPY_VERSION="$PYTHON_NUMPY_VERSION" \
)

echo 'Build for Py2'
(cd "${OPENCV_BUILD}"; make -j8 "${OPENCV_TARGET}")

# Moving back to opencv-python
echo 'Copying *.so for Py2'
WHEEL_STAGING="${WORKDIR}/wheel"
mkdir -p "${WHEEL_STAGING}"

# Mimic "opencv-python"'s "find_version.py", but with our version.
echo "opencv_version = '${OPENCV_VERSION}'" > "${WHEEL_STAGING}/cv_version.py"

for src in requirements.txt setup.py README.rst cv2; do
  (cd "${PY_OPENCV_ROOT}" && cp -R $src "${WHEEL_STAGING}")
done
cp "${OPENCV_BUILD}/lib/cv2.so" "${WHEEL_STAGING}/cv2/"

# Build wheel
echo 'Build wheel'
(cd "${WHEEL_STAGING}"; python setup.py bdist_wheel)
