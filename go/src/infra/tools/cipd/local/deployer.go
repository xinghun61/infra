// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package local

import (
	"crypto/sha1"
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"github.com/luci/luci-go/common/logging"

	"infra/tools/cipd/common"
)

// TODO(vadimsh): Make it work on Windows.

// TODO(vadimsh): How to handle path conflicts between two packages? Currently
// the last one installed wins.

// File system layout of a site directory <root>:
// <root>/.cipd/pkgs/
//   <package name digest>/
//     _current -> symlink to fea3ab83440e9dfb813785e16d4101f331ed44f4
//     fea3ab83440e9dfb813785e16d4101f331ed44f4/
//       bin/
//         tool
//         ...
//       ...
// bin/
//    tool -> symlink to ../.cipd/pkgs/<package name digest>/_current/bin/tool
//    ...
//
// Where <package name digest> is derived from a package name. It doesn't have
// to be reversible though, since the package name is still stored in the
// installed package manifest and can be read from there.
//
// Some efforts are made to make sure that during the deployment a window of
// inconsistency in the file system is as small as possible.

// Deployer knows how to unzip and place packages into site root directory.
type Deployer interface {
	// DeployInstance installs a specific instance of a package into a site root
	// directory. It unpacks the package into <root>/.cipd/pkgs/*, and rearranges
	// symlinks to point to unpacked files. It tries to make it as "atomic" as
	// possible. Returns information about the deployed instance.
	DeployInstance(PackageInstance) (common.Pin, error)

	// CheckDeployed checks whether a given package is deployed and returns
	// information about installed version if it is or error if not.
	CheckDeployed(packageName string) (common.Pin, error)

	// FindDeployed returns a list of packages deployed to a site root.
	FindDeployed() (out []common.Pin, err error)

	// RemoveDeployed deletes a package given its name.
	RemoveDeployed(packageName string) error

	// TempFile returns os.File located in <root>/tmp/*.
	TempFile(prefix string) (*os.File, error)
}

// NewDeployer return default Deployer implementation.
func NewDeployer(root string, logger logging.Logger) Deployer {
	var err error
	if root == "" {
		err = fmt.Errorf("Site root path is not provided")
	} else {
		root, err = filepath.Abs(filepath.Clean(root))
	}
	if err != nil {
		return errDeployer{err}
	}
	if logger == nil {
		logger = logging.Null()
	}
	return &deployerImpl{NewFileSystem(root, logger), logger}
}

////////////////////////////////////////////////////////////////////////////////
// Implementation that returns error on all requests.

type errDeployer struct{ err error }

func (d errDeployer) DeployInstance(PackageInstance) (common.Pin, error)   { return common.Pin{}, d.err }
func (d errDeployer) CheckDeployed(packageName string) (common.Pin, error) { return common.Pin{}, d.err }
func (d errDeployer) FindDeployed() (out []common.Pin, err error)          { return nil, d.err }
func (d errDeployer) RemoveDeployed(packageName string) error              { return d.err }
func (d errDeployer) TempFile(prefix string) (*os.File, error)             { return nil, d.err }

////////////////////////////////////////////////////////////////////////////////
// Real deployer implementation.

// packagesDir is a subdirectory of site root to extract packages to.
const packagesDir = siteServiceDir + "/pkgs"

// currentSymlink is a name of a symlink that points to latest deployed version.
const currentSymlink = "_current"

// deployerImpl implements Deployer interface.
type deployerImpl struct {
	fs     FileSystem
	logger logging.Logger
}

func (d *deployerImpl) DeployInstance(inst PackageInstance) (common.Pin, error) {
	pin := inst.Pin()
	d.logger.Infof("Deploying %s into %s", pin, d.fs.Root())

	// Be paranoid.
	if err := common.ValidatePin(pin); err != nil {
		return common.Pin{}, err
	}
	if _, err := d.fs.EnsureDirectory(d.fs.Root()); err != nil {
		return common.Pin{}, err
	}

	// Remember currently deployed version (to remove it later). Do not freak out
	// if it's not there (prevID is "" in that case).
	oldFiles := makeStringSet()
	prevID := d.findDeployedInstance(pin.PackageName, oldFiles)

	// Extract new version to a final destination.
	newFiles := makeStringSet()
	destPath, err := d.deployInstance(inst, newFiles)
	if err != nil {
		return common.Pin{}, err
	}

	// Switch '_current' symlink to point to a new package instance. It is a
	// point of no return. The function must not fail going forward.
	mainSymlinkPath := d.packagePath(pin.PackageName, currentSymlink)
	err = d.fs.EnsureSymlink(mainSymlinkPath, pin.InstanceID)
	if err != nil {
		d.fs.EnsureDirectoryGone(destPath)
		return common.Pin{}, err
	}

	// Asynchronously remove previous version (best effort).
	wg := sync.WaitGroup{}
	defer wg.Wait()
	if prevID != "" && prevID != pin.InstanceID {
		wg.Add(1)
		go func() {
			defer wg.Done()
			d.fs.EnsureDirectoryGone(d.packagePath(pin.PackageName, prevID))
		}()
	}

	d.logger.Infof("Adjusting symlinks for %s", pin.PackageName)

	// Make symlinks in the site directory for all new files. Reference a package
	// root via '_current' symlink (instead of direct destPath), to make
	// subsequent updates 'more atomic' (since they'll need to switch only
	// '_current' symlink to update _all_ files in the site root at once).
	d.linkFilesToRoot(mainSymlinkPath, newFiles)

	// Delete symlinks to files no longer needed i.e. set(old) - set(new).
	for relPath := range oldFiles.diff(newFiles) {
		d.fs.EnsureFileGone(filepath.Join(d.fs.Root(), relPath))
	}

	// Verify it's all right, read the manifest.
	newPin, err := d.CheckDeployed(pin.PackageName)
	if err == nil && newPin.InstanceID != pin.InstanceID {
		err = fmt.Errorf("Other instance (%s) was deployed concurrently", newPin.InstanceID)
	}
	if err == nil {
		d.logger.Infof("Successfully deployed %s", pin)
	} else {
		d.logger.Errorf("Failed to deploy %s: %s", pin, err)
	}
	return newPin, err
}

func (d *deployerImpl) CheckDeployed(pkg string) (common.Pin, error) {
	pin, err := readPackageState(d.packagePath(pkg))
	if err == nil && pin.PackageName != pkg {
		err = fmt.Errorf("Package path and package name in the manifest do not match")
	}
	return pin, err
}

func (d *deployerImpl) FindDeployed() (out []common.Pin, err error) {
	// Directories with packages are direct children of .cipd/pkgs/.
	pkgs := filepath.Join(d.fs.Root(), filepath.FromSlash(packagesDir))
	infos, err := ioutil.ReadDir(pkgs)
	if err != nil {
		if os.IsNotExist(err) {
			err = nil
			return
		}
		return
	}

	// Read the package name from the package manifest. Skip broken stuff.
	found := map[string]common.Pin{}
	keys := []string{}
	for _, info := range infos {
		// Attempt to read the manifest. If it is there -> valid package is found.
		if info.IsDir() {
			pin, err := readPackageState(filepath.Join(pkgs, info.Name()))
			if err == nil {
				// Ignore duplicate entries, they can appear if someone messes with
				// pkgs/* structure manually.
				if _, ok := found[pin.PackageName]; !ok {
					keys = append(keys, pin.PackageName)
					found[pin.PackageName] = pin
				}
			}
		}
	}

	// Sort by package name.
	sort.Strings(keys)
	out = make([]common.Pin, len(found))
	for i, k := range keys {
		out[i] = found[k]
	}
	return
}

func (d *deployerImpl) RemoveDeployed(packageName string) error {
	d.logger.Infof("Removing %s from %s", packageName, d.fs.Root())

	// Be paranoid.
	err := common.ValidatePackageName(packageName)
	if err != nil {
		return err
	}

	// Grab list of files in currently deployed package to unlink them from root.
	files := makeStringSet()
	instanceID := d.findDeployedInstance(packageName, files)

	// If was installed, removed symlinks pointing to the package files.
	if instanceID != "" {
		for relPath := range files {
			d.fs.EnsureFileGone(filepath.Join(d.fs.Root(), relPath))
		}
	}

	// Ensure all garbage is gone even if instanceID == "" was returned.
	return d.fs.EnsureDirectoryGone(d.packagePath(packageName))
}

func (d *deployerImpl) TempFile(prefix string) (*os.File, error) {
	dir, err := d.fs.EnsureDirectory(filepath.Join(d.fs.Root(), siteServiceDir, "tmp"))
	if err != nil {
		return nil, err
	}
	return ioutil.TempFile(dir, prefix)
}

////////////////////////////////////////////////////////////////////////////////
// Utility methods.

// findDeployedInstance returns instanceID of a currently deployed package
// instance and finds all files in it (adding them to 'files' set). Returns ""
// if nothing is deployed. File paths in 'files' are relative to package root.
func (d *deployerImpl) findDeployedInstance(pkg string, files stringSet) string {
	state, err := d.CheckDeployed(pkg)
	if err != nil {
		return ""
	}
	scanPackageDir(d.packagePath(pkg, state.InstanceID), files)
	return state.InstanceID
}

// deployInstance atomically extracts a package instance to its final
// destination and returns a path to it. It writes a list of extracted files
// to 'files'. File paths in 'files' are relative to package root.
func (d *deployerImpl) deployInstance(inst PackageInstance, files stringSet) (string, error) {
	// Extract new version to a final destination. ExtractPackageInstance knows
	// how to build full paths and how to atomically extract a package. No need
	// to delete garbage if it fails.
	destPath := d.packagePath(inst.Pin().PackageName, inst.Pin().InstanceID)
	err := ExtractInstance(inst, NewFileSystemDestination(destPath, d.fs))
	if err != nil {
		return "", err
	}
	// Enumerate files inside. Nuke it and fail if it's unreadable.
	err = scanPackageDir(d.packagePath(inst.Pin().PackageName, inst.Pin().InstanceID), files)
	if err != nil {
		d.fs.EnsureDirectoryGone(destPath)
		return "", err
	}
	return destPath, err
}

// linkFilesToRoot makes symlinks in root that point to files in packageRoot.
// All targets are specified by 'files' as paths relative to packageRoot. This
// function is best effort and thus doesn't return errors.
func (d *deployerImpl) linkFilesToRoot(packageRoot string, files stringSet) {
	for relPath := range files {
		// E.g <root>/bin/tool.
		symlinkAbs := filepath.Join(d.fs.Root(), relPath)
		// E.g. <root>/.cipd/pkgs/name/_current/bin/tool.
		targetAbs := filepath.Join(packageRoot, relPath)
		// E.g. ../.cipd/pkgs/name/_current/bin/tool.
		targetRel, err := filepath.Rel(filepath.Dir(symlinkAbs), targetAbs)
		if err != nil {
			d.logger.Warningf("Can't get relative path from %s to %s", filepath.Dir(symlinkAbs), targetAbs)
			continue
		}
		err = d.fs.EnsureSymlink(symlinkAbs, targetRel)
		if err != nil {
			d.logger.Warningf("Failed to create symlink for %s", relPath)
			continue
		}
	}
}

// packagePath joins paths together to return absolute path to .cipd/pkgs sub path.
func (d *deployerImpl) packagePath(pkg string, rest ...string) string {
	root := filepath.Join(d.fs.Root(), filepath.FromSlash(packagesDir), packageNameDigest(pkg))
	result := filepath.Join(append([]string{root}, rest...)...)

	// Be paranoid and check that everything is inside .cipd directory.
	abs, err := filepath.Abs(result)
	if err != nil {
		msg := fmt.Sprintf("Can't get absolute path of '%s'", result)
		d.logger.Errorf("%s", msg)
		panic(msg)
	}
	if !isSubpath(abs, root) {
		msg := fmt.Sprintf("Wrong path %s outside of root %s", abs, root)
		d.logger.Errorf("%s", msg)
		panic(msg)
	}
	return result
}

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// packageNameDigest returns a filename to use for naming a package directory in
// the file system. Using package names as is can introduce problems on file
// systems with path length limits (on Windows in particular). Returns last two
// components of the package name + stripped SHA1 of the whole package name.
func packageNameDigest(pkg string) string {
	// Be paranoid.
	err := common.ValidatePackageName(pkg)
	if err != nil {
		panic(err.Error())
	}

	// Grab stripped SHA1 of the full package name.
	h := sha1.New()
	h.Write([]byte(pkg))
	hash := base64.URLEncoding.EncodeToString(h.Sum(nil))[:10]

	// Grab last <= 2 components of the package path.
	chunks := strings.Split(pkg, "/")
	if len(chunks) > 2 {
		chunks = chunks[len(chunks)-2:]
	}

	// Join together with '_' as separator.
	chunks = append(chunks, hash)
	return strings.Join(chunks, "_")
}

// readPackageState reads package manifest of a deployed package instance and
// returns corresponding Pin object.
func readPackageState(packageDir string) (common.Pin, error) {
	// Resolve _current symlink to a concrete instance ID.
	current, err := os.Readlink(filepath.Join(packageDir, currentSymlink))
	if err != nil {
		return common.Pin{}, err
	}
	err = common.ValidateInstanceID(current)
	if err != nil {
		return common.Pin{}, fmt.Errorf("Symlink target doesn't look like a valid instance id")
	}
	// Read the manifest from the instance directory.
	manifestPath := filepath.Join(packageDir, current, filepath.FromSlash(manifestName))
	r, err := os.Open(manifestPath)
	if err != nil {
		return common.Pin{}, err
	}
	defer r.Close()
	manifest, err := readManifest(r)
	if err != nil {
		return common.Pin{}, err
	}
	return common.Pin{
		PackageName: manifest.PackageName,
		InstanceID:  current,
	}, nil
}

// scanPackageDir finds a set of regular files (and symlinks) in a package
// instance directory. Adds paths relative to 'dir' to 'out'. Skips package
// service directories (.cipdpkg and .cipd) since they contain package deployer
// gut files, not something that needs to be deployed.
func scanPackageDir(dir string, out stringSet) error {
	return filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(dir, path)
		if err != nil {
			return err
		}
		if rel == packageServiceDir || rel == siteServiceDir {
			return filepath.SkipDir
		}
		if info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
			out.add(rel)
		}
		return nil
	})
}

////////////////////////////////////////////////////////////////////////////////
// Simple stringSet implementation for keeping a set of filenames.

type stringSet map[string]struct{}

func makeStringSet() stringSet {
	return make(stringSet)
}

// add adds an element to the string set.
func (a stringSet) add(elem string) {
	a[elem] = struct{}{}
}

// diff returns set(a) - set(b).
func (a stringSet) diff(b stringSet) stringSet {
	out := makeStringSet()
	for elem := range a {
		if _, ok := b[elem]; !ok {
			out.add(elem)
		}
	}
	return out
}
