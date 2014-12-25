// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// TODO: Make it work on Windows, verify it works on Mac.

// TODO: How to handle path conflicts between two packages? Currently the last
// installed wins.

// File system layout of a site directory <root>:
// <root>/.cipd/pkgs/
//   <package name>/
//     _current -> symlink to fea3ab83440e9dfb813785e16d4101f331ed44f4
//     fea3ab83440e9dfb813785e16d4101f331ed44f4/
//       bin/
//         tool
//         ...
//       ...
// bin/
//    tool -> symlink to ../.cipd/pkgs/<package name>/_current/bin/tool
//    ...
//
// Some efforts are made to make sure that during the deployment a window of
// inconsistency in the file system is as small as possible.

// Subdirectory of site root to extract packages to.
const packagesDir = siteServiceDir + "/pkgs"

// Name of a symlink that points to latest deployed version.
const currentSymlink = "_current"

// DeployedPackageInfo contains information about single deployed package.
type DeployedPackageInfo struct {
	// Id of the original package file: package.InstanceID().
	InstanceID string
	// Original package's manifest.
	Manifest Manifest
}

// Deploy installs a specific instance of a package (identified by InstanceID())
// into a site root directory. It unpacks the package into <root>/.cipd/pkgs/*,
// and rearranges symlinks to point to unpacked files. It tries to make it as
// "atomic" as possibly.
func Deploy(root string, p Package) (info DeployedPackageInfo, err error) {
	root, err = filepath.Abs(filepath.Clean(root))
	if err != nil {
		return
	}
	log.Infof("Deploying %s:%s into %s", p.Name(), p.InstanceID(), root)

	// Be paranoid.
	err = ValidatePackageName(p.Name())
	if err != nil {
		return
	}
	err = ValidateInstanceID(p.InstanceID())
	if err != nil {
		return
	}
	if !p.Signed() {
		err = fmt.Errorf("Package is not signed: %s", p.Name())
		return
	}

	// Remember currently deployed version (to remove it later). Do not freak out
	// if it's not there (prevID is "" in that case).
	oldFiles := makeStringSet()
	prevID := findDeployedInstance(root, p.Name(), oldFiles)

	// Extract new version to a final destination.
	newFiles := makeStringSet()
	destPath, err := deployInstance(root, p, newFiles)
	if err != nil {
		return
	}

	// Switch '_current' symlink to point to a new package instance. It is a
	// point of no return. The function must not fail going forward.
	mainSymlinkPath := packagePath(root, p.Name(), currentSymlink)
	err = ensureSymlink(mainSymlinkPath, p.InstanceID())
	if err != nil {
		ensureDirectoryGone(destPath)
		return
	}

	// Asynchronously remove previous version (best effort).
	wg := sync.WaitGroup{}
	defer wg.Wait()
	if prevID != "" && prevID != p.InstanceID() {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ensureDirectoryGone(packagePath(root, p.Name(), prevID))
		}()
	}

	log.Infof("Adjusting symlinks for %s", p.Name())

	// Make symlinks in the site directory for all new files. Reference a package
	// root via '_current' symlink (instead of direct destPath), to make
	// subsequent updates 'more atomic' (since they'll need to switch only
	// '_current' symlink to update _all_ files in the site root at once).
	linkFilesToRoot(root, mainSymlinkPath, newFiles)

	// Delete symlinks to files no longer needed i.e. set(old) - set(new).
	for relPath := range oldFiles.diff(newFiles) {
		absPath := filepath.Join(root, relPath)
		err = os.Remove(absPath)
		if err != nil {
			log.Warnf("Failed to remove %s", absPath)
		}
	}

	// Verify it's all right, read the manifest.
	info, err = CheckDeployed(root, p.Name())
	if err == nil && info.InstanceID != p.InstanceID() {
		err = fmt.Errorf("Other package instance (%s) was deployed concurrently", info.InstanceID)
	}
	if err == nil {
		log.Infof("Successfully deployed %s:%s", p.Name(), p.InstanceID())
	} else {
		log.Errorf("Failed to deploy %s:%s: %s", p.Name(), p.InstanceID(), err.Error())
	}
	return
}

// CheckDeployed checks whether a given package is deployed and returns
// information about it if it is.
func CheckDeployed(root string, pkg string) (info DeployedPackageInfo, err error) {
	// Be paranoid.
	err = ValidatePackageName(pkg)
	if err != nil {
		return
	}

	// Resolve "_current" symlink to a concrete id.
	current, err := os.Readlink(packagePath(root, pkg, currentSymlink))
	if err != nil {
		return
	}
	err = ValidateInstanceID(current)
	if err != nil {
		err = fmt.Errorf("Symlink target doesn't look like a valid package id")
		return
	}

	// Read manifest file, verify it's sane.
	manifestPath := packagePath(root, pkg, current, filepath.FromSlash(manifestName))
	r, err := os.Open(manifestPath)
	if err != nil {
		return
	}
	defer r.Close()
	manifest, err := readManifest(r)
	if err != nil {
		return
	}
	if manifest.PackageName != pkg {
		err = fmt.Errorf("Package path and package name in the manifest do not match")
		return
	}

	info = DeployedPackageInfo{
		InstanceID: current,
		Manifest:   manifest,
	}
	return
}

////////////////////////////////////////////////////////////////////////////////
// Utility functions.

// findDeployedInstance returns instanceID of a currently deployed package
// instance and finds all files in it (adding them to 'files' set). Returns ""
// if nothing is deployed. File paths in 'files' are relative to package root.
func findDeployedInstance(root string, pkg string, files stringSet) string {
	info, err := CheckDeployed(root, pkg)
	if err != nil {
		return ""
	}
	log.Infof("Enumerating files in %s:%s", pkg, info.InstanceID)
	scanPackageDir(packagePath(root, pkg, info.InstanceID), files)
	return info.InstanceID
}

// deployInstance atomically extracts a package instance to its final
// destination and returns a path to it. It writes a list of extracted files
// to 'files'. File paths in 'files' are relative to package root.
func deployInstance(root string, p Package, files stringSet) (string, error) {
	// Extract new version to a final destination. ExtractPackage knows how to
	// build full paths and how to atomically extract a package. No need to delete
	// garbage if it fails.
	destPath := packagePath(root, p.Name(), p.InstanceID())
	err := ExtractPackage(p, NewFileSystemDestination(destPath))
	if err != nil {
		return "", err
	}
	// Enumerate files inside. Nuke it and fail if it's unreadable.
	err = scanPackageDir(packagePath(root, p.Name(), p.InstanceID()), files)
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
	// Be paranoid.
	err := ValidatePackageName(pkg)
	if err != nil {
		panic(err.Error())
	}

	root, err = filepath.Abs(filepath.Clean(root))
	if err != nil {
		panic(fmt.Sprintf("Can't get absolute path of '%s'", root))
	}
	root = filepath.Join(root, filepath.FromSlash(packagesDir), filepath.FromSlash(pkg))
	result := filepath.Join(append([]string{root}, rest...)...)

	// Be more paranoid and check that everything is inside .cipd directory.
	abs, err := filepath.Abs(result)
	if err != nil {
		panic(fmt.Sprintf("Can't get absolute path of '%s'", result))
	}
	if !strings.HasPrefix(abs, root) {
		panic(fmt.Sprintf("Wrong path %s outside of root %s", abs, root))
	}
	return result
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
