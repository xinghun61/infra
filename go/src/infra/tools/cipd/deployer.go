// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

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
	"time"
)

// TODO(vadimsh): Make it work on Windows, verify it works on Mac.

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

// Subdirectory of site root to extract packages to.
const packagesDir = siteServiceDir + "/pkgs"

// Name of a symlink that points to latest deployed version.
const currentSymlink = "_current"

// PackageState contains information about single deployed package.
type PackageState struct {
	// PackageName identifies the package.
	PackageName string
	// InstanceID is ID of the installed package instance (SHA1 of package contents).
	InstanceID string
}

// DeployInstance installs a specific instance of a package (identified by
// InstanceID()) into a site root directory. It unpacks the package into
// <root>/.cipd/pkgs/*, and rearranges symlinks to point to unpacked files.
// It tries to make it as "atomic" as possibly.
func DeployInstance(root string, inst PackageInstance) (state PackageState, err error) {
	root, err = filepath.Abs(filepath.Clean(root))
	if err != nil {
		return
	}
	log.Infof("Deploying %s:%s into %s", inst.PackageName(), inst.InstanceID(), root)

	// Be paranoid.
	err = ValidatePackageName(inst.PackageName())
	if err != nil {
		return
	}
	err = ValidateInstanceID(inst.InstanceID())
	if err != nil {
		return
	}

	// Remember currently deployed version (to remove it later). Do not freak out
	// if it's not there (prevID is "" in that case).
	oldFiles := makeStringSet()
	prevID := findDeployedInstance(root, inst.PackageName(), oldFiles)

	// Extract new version to a final destination.
	newFiles := makeStringSet()
	destPath, err := deployInstance(root, inst, newFiles)
	if err != nil {
		return
	}

	// Switch '_current' symlink to point to a new package instance. It is a
	// point of no return. The function must not fail going forward.
	mainSymlinkPath := packagePath(root, inst.PackageName(), currentSymlink)
	err = ensureSymlink(mainSymlinkPath, inst.InstanceID())
	if err != nil {
		ensureDirectoryGone(destPath)
		return
	}

	// Asynchronously remove previous version (best effort).
	wg := sync.WaitGroup{}
	defer wg.Wait()
	if prevID != "" && prevID != inst.InstanceID() {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ensureDirectoryGone(packagePath(root, inst.PackageName(), prevID))
		}()
	}

	log.Infof("Adjusting symlinks for %s", inst.PackageName())

	// Make symlinks in the site directory for all new files. Reference a package
	// root via '_current' symlink (instead of direct destPath), to make
	// subsequent updates 'more atomic' (since they'll need to switch only
	// '_current' symlink to update _all_ files in the site root at once).
	linkFilesToRoot(root, mainSymlinkPath, newFiles)

	// Delete symlinks to files no longer needed i.e. set(old) - set(new).
	for relPath := range oldFiles.diff(newFiles) {
		ensureFileGone(filepath.Join(root, relPath))
	}

	// Verify it's all right, read the manifest.
	state, err = CheckDeployed(root, inst.PackageName())
	if err == nil && state.InstanceID != inst.InstanceID() {
		err = fmt.Errorf("Other package instance (%s) was deployed concurrently", state.InstanceID)
	}
	if err == nil {
		log.Infof("Successfully deployed %s:%s", inst.PackageName(), inst.InstanceID())
	} else {
		log.Errorf("Failed to deploy %s:%s: %s", inst.PackageName(), inst.InstanceID(), err.Error())
	}
	return
}

// CheckDeployed checks whether a given package is deployed and returns
// information about it if it is.
func CheckDeployed(root string, pkg string) (state PackageState, err error) {
	state, err = readPackageState(packagePath(root, pkg))
	if err != nil {
		return
	}
	if state.PackageName != pkg {
		err = fmt.Errorf("Package path and package name in the manifest do not match")
	}
	return
}

// FindDeployed returns a list of packages deployed to a site root.
func FindDeployed(root string) (out []PackageState, err error) {
	root, err = filepath.Abs(filepath.Clean(root))
	if err != nil {
		return
	}

	// Directories with packages are direct children of .cipd/pkgs/.
	pkgs := filepath.Join(root, filepath.FromSlash(packagesDir))
	infos, err := ioutil.ReadDir(pkgs)
	if err != nil {
		if os.IsNotExist(err) {
			err = nil
			return
		}
		return
	}

	// Read the package name from the package manifest. Skip broken stuff.
	found := make(map[string]PackageState)
	keys := []string{}
	for _, info := range infos {
		// Attempt to read the manifest. If it is there -> valid package is found.
		if info.IsDir() {
			state, err := readPackageState(filepath.Join(pkgs, info.Name()))
			if err == nil {
				// Ignore duplicate entries, they can appear if someone messes with
				// pkgs/* structure manually.
				if _, ok := found[state.PackageName]; !ok {
					keys = append(keys, state.PackageName)
					found[state.PackageName] = state
				}
			}
		}
	}

	// Sort by package name.
	sort.Strings(keys)
	out = make([]PackageState, len(found))
	for i, k := range keys {
		out[i] = found[k]
	}
	return
}

// RemoveDeployed deletes a package given its name.
func RemoveDeployed(root string, packageName string) error {
	root, err := filepath.Abs(filepath.Clean(root))
	if err != nil {
		return err
	}
	log.Infof("Removing %s from %s", packageName, root)

	// Be paranoid.
	err = ValidatePackageName(packageName)
	if err != nil {
		return err
	}

	// Grab list of files in currently deployed package to unlink them from root.
	files := makeStringSet()
	instanceID := findDeployedInstance(root, packageName, files)

	// If was installed, removed symlinks pointing to the package files.
	if instanceID != "" {
		for relPath := range files {
			ensureFileGone(filepath.Join(root, relPath))
		}
	}

	// Ensure all garbage is gone even if instanceID == "" was returned.
	return ensureDirectoryGone(packagePath(root, packageName))
}

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// findDeployedInstance returns instanceID of a currently deployed package
// instance and finds all files in it (adding them to 'files' set). Returns ""
// if nothing is deployed. File paths in 'files' are relative to package root.
func findDeployedInstance(root string, pkg string, files stringSet) string {
	state, err := CheckDeployed(root, pkg)
	if err != nil {
		return ""
	}
	scanPackageDir(packagePath(root, pkg, state.InstanceID), files)
	return state.InstanceID
}

// deployInstance atomically extracts a package instance to its final
// destination and returns a path to it. It writes a list of extracted files
// to 'files'. File paths in 'files' are relative to package root.
func deployInstance(root string, inst PackageInstance, files stringSet) (string, error) {
	// Extract new version to a final destination. ExtractPackageInstance knows
	// how to build full paths and how to atomically extract a package. No need
	// to delete garbage if it fails.
	destPath := packagePath(root, inst.PackageName(), inst.InstanceID())
	err := ExtractInstance(inst, NewFileSystemDestination(destPath))
	if err != nil {
		return "", err
	}
	// Enumerate files inside. Nuke it and fail if it's unreadable.
	err = scanPackageDir(packagePath(root, inst.PackageName(), inst.InstanceID()), files)
	if err != nil {
		ensureDirectoryGone(destPath)
		return "", err
	}
	return destPath, err
}

// linkFilesToRoot makes symlinks in root that point to files in packageRoot.
// All targets are specified by 'files' as paths relative to packageRoot. This
// function is best effort and thus doesn't return errors.
func linkFilesToRoot(root string, packageRoot string, files stringSet) {
	for relPath := range files {
		// E.g <root>/bin/tool.
		symlinkAbs := filepath.Join(root, relPath)
		// E.g. <root>/.cipd/pkgs/name/_current/bin/tool.
		targetAbs := filepath.Join(packageRoot, relPath)
		// E.g. ../.cipd/pkgs/name/_current/bin/tool.
		targetRel, err := filepath.Rel(filepath.Dir(symlinkAbs), targetAbs)
		if err != nil {
			log.Warnf("Can't get relative path from %s to %s", filepath.Dir(symlinkAbs), targetAbs)
			continue
		}
		err = ensureSymlink(symlinkAbs, targetRel)
		if err != nil {
			log.Warnf("Failed to create symlink for %s", relPath)
			continue
		}
	}
}

// packagePath joins paths together to return absolute path to .cipd/pkgs sub path.
func packagePath(root string, pkg string, rest ...string) string {
	root, err := filepath.Abs(filepath.Clean(root))
	if err != nil {
		panic(fmt.Sprintf("Can't get absolute path of '%s'", root))
	}
	root = filepath.Join(root, filepath.FromSlash(packagesDir), packageNameDigest(pkg))
	result := filepath.Join(append([]string{root}, rest...)...)

	// Be paranoid and check that everything is inside .cipd directory.
	abs, err := filepath.Abs(result)
	if err != nil {
		panic(fmt.Sprintf("Can't get absolute path of '%s'", result))
	}
	if !strings.HasPrefix(abs, root) {
		panic(fmt.Sprintf("Wrong path %s outside of root %s", abs, root))
	}
	return result
}

// packageNameDigest returns a filename to use for naming a package directory in
// the file system. Using package names as is can introduce problems on file
// systems with path length limits (on Windows in particular). Returns last two
// components of the package name + stripped SHA1 of the whole package name.
func packageNameDigest(pkg string) string {
	// Be paranoid.
	err := ValidatePackageName(pkg)
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
// returns corresponding PackageState object.
func readPackageState(packageDir string) (state PackageState, err error) {
	// Resolve _current symlink to a concrete instance ID.
	current, err := os.Readlink(filepath.Join(packageDir, currentSymlink))
	if err != nil {
		return
	}
	err = ValidateInstanceID(current)
	if err != nil {
		err = fmt.Errorf("Symlink target doesn't look like a valid instance id")
		return
	}
	// Read the manifest from the instance directory.
	manifestPath := filepath.Join(packageDir, current, filepath.FromSlash(manifestName))
	r, err := os.Open(manifestPath)
	if err != nil {
		return
	}
	defer r.Close()
	manifest, err := readManifest(r)
	if err != nil {
		return
	}
	state = PackageState{
		PackageName: manifest.PackageName,
		InstanceID:  current,
	}
	return
}

// ensureSymlink atomically creates a symlink pointing to a target. It will
// create full directory path if necessary.
func ensureSymlink(symlink string, target string) error {
	// Already set?
	existing, err := os.Readlink(symlink)
	if err != nil && existing == target {
		return nil
	}

	// Make sure path exists.
	err = os.MkdirAll(filepath.Dir(symlink), 0777)
	if err != nil {
		return err
	}

	// Create a new symlink file, can't modify existing one.
	temp := fmt.Sprintf("%s_%v", symlink, time.Now().UnixNano())
	err = os.Symlink(target, temp)
	if err != nil {
		return err
	}

	// Atomically replace current symlink with a new one.
	err = os.Rename(temp, symlink)
	if err != nil {
		os.Remove(temp)
		return err
	}

	return nil
}

// scanPackageDir finds a set of regular files found in a directory with paths
// relative to that directory to be symlinked into the site root. Skips package
// service directories (.cipdpkg and .cipd) since they contains package deployer
// gut files, not something that needs to be deployed.
func scanPackageDir(root string, out stringSet) error {
	return filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		if rel == packageServiceDir || rel == siteServiceDir {
			return filepath.SkipDir
		}
		if info.Mode().IsRegular() {
			out.add(rel)
		}
		return nil
	})
}

// ensureDirectoryGone removes the directory as instantly as possible by
// renaming it first and only then recursively deleting.
func ensureDirectoryGone(path string) error {
	temp := fmt.Sprintf("%s_%v", path, time.Now().UnixNano())
	err := os.Rename(path, temp)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Warnf("Failed to rename directory %s: %v", path, err)
			return err
		}
		return nil
	}
	err = os.RemoveAll(temp)
	if err != nil {
		log.Warnf("Failed to remove directory %s: %v", temp, err)
		return err
	}
	return nil
}

// ensureFileGone removes file, logging the errors (if any).
func ensureFileGone(path string) error {
	err := os.Remove(path)
	if err != nil && !os.IsNotExist(err) {
		log.Warnf("Failed to remove %s", path)
		return err
	}
	return nil
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
