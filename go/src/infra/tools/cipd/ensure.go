// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bufio"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"infra/libs/logging"
)

// ParseDesiredState parses text file that describes what should be installed
// by EnsurePackages function. It is a text file where each line has a form:
// <package name> <desired instance ID>
// Whitespaces are ignored. Lines that start with '#' are ignored.
func ParseDesiredState(r io.Reader) ([]PackageState, error) {
	lineNo := 0
	makeError := func(msg string) error {
		return fmt.Errorf("Failed to parse desired state (line %d): %s", lineNo, msg)
	}

	out := []PackageState{}
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		lineNo++

		// Split each line into words, ignore white space.
		tokens := []string{}
		for _, chunk := range strings.Split(scanner.Text(), " ") {
			chunk = strings.TrimSpace(chunk)
			if chunk != "" {
				tokens = append(tokens, chunk)
			}
		}

		// Skip empty lines or lines starting with '#'.
		if len(tokens) == 0 || tokens[0][0] == '#' {
			continue
		}

		// Each line has a format "<package name> <instance id>".
		if len(tokens) != 2 {
			return nil, makeError("expecting '<package name> <instance id>' line")
		}
		err := ValidatePackageName(tokens[0])
		if err != nil {
			return nil, makeError(err.Error())
		}
		err = ValidateInstanceID(tokens[1])
		if err != nil {
			return nil, makeError(err.Error())
		}

		// Good enough.
		out = append(out, PackageState{
			PackageName: tokens[0],
			InstanceID:  tokens[1],
		})
	}

	return out, nil
}

// EnsurePackagesOptions contains parameters for EnsurePackages calls.
type EnsurePackagesOptions struct {
	// ServiceURL is root URL of the backend service, or "" to use default service.
	ServiceURL string
	// ClientFactory knows how to make authenticated http.Client when it is needed. Called lazily.
	ClientFactory func() (*http.Client, error)
	// Log is a logger to use for logs, default is logging.DefaultLogger.
	Log logging.Logger

	// Root is a site root directory to modify. Will be created if missing.
	Root string
	// Packages describes the desired state of the site root directory.
	Packages []PackageState
}

// EnsurePackages is high level interface for installing, removing and updating
// of packages inside some installation site root. Given a description of
// what packages (and versions) should be installed it will do all necessary
// actions to bring the state of the site root to desired one.
func EnsurePackages(opts EnsurePackagesOptions) error {
	// Make sure a package is specified only once.
	seen := make(map[string]bool)
	for _, p := range opts.Packages {
		if seen[p.PackageName] {
			return fmt.Errorf("Package %s is specified twice", p.PackageName)
		}
		seen[p.PackageName] = true
	}

	// Fill in default options.
	if opts.ServiceURL == "" {
		opts.ServiceURL = DefaultServiceURL()
	}
	if opts.Log == nil {
		opts.Log = logging.DefaultLogger
	}
	log := opts.Log

	// Ensure site root is a directory (or missing).
	root, err := filepath.Abs(filepath.Clean(opts.Root))
	if err != nil {
		return err
	}
	stat, err := os.Stat(root)
	if err == nil && !stat.IsDir() {
		return fmt.Errorf("Path %s is not a directory", opts.Root)
	}
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	rootExists := (err == nil)

	// Enumerate existing packages (only if root already exists).
	existing := []PackageState{}
	if rootExists {
		existing, err = FindDeployed(root)
		if err != nil {
			log.Errorf("Failed to enumerate installed packages: %s", err)
			return err
		}
	}

	// Figure out what needs to be updated and deleted, log it.
	toDeploy, toDelete := buildActionPlan(opts.Packages, existing)
	if len(toDeploy) == 0 && len(toDelete) == 0 {
		log.Infof("Everything is up-to-date.")
		return nil
	}
	if len(toDeploy) != 0 {
		log.Infof("Packages to be installed:")
		for _, state := range toDeploy {
			log.Infof("  %s:%s", state.PackageName, state.InstanceID)
		}
	}
	if len(toDelete) != 0 {
		log.Infof("Packages to be removed:")
		for _, state := range toDelete {
			log.Infof("  %s", state.PackageName)
		}
	}

	// Create the site root directory before installing anything there.
	if len(toDeploy) != 0 && !rootExists {
		err = os.MkdirAll(root, 0777)
		if err != nil {
			return err
		}
	}

	// Updating packages requires interaction with the server, create the client.
	client := http.DefaultClient
	if len(toDeploy) != 0 && opts.ClientFactory != nil {
		client, err = opts.ClientFactory()
		if err != nil {
			return err
		}
	}

	// Remove all unneeded stuff.
	errors := []error{}
	for _, state := range toDelete {
		err = RemoveDeployed(root, state.PackageName)
		if err != nil {
			log.Errorf("Failed to remove %s - %s", state.PackageName, err)
			errors = append(errors, err)
		}
	}

	// Install all new stuff.
	for _, state := range toDeploy {
		err = FetchAndDeployInstance(root, FetchInstanceOptions{
			ServiceURL:  opts.ServiceURL,
			Client:      client,
			Log:         opts.Log,
			PackageName: state.PackageName,
			InstanceID:  state.InstanceID,
		})
		if err != nil {
			log.Errorf("Failed to install %s:%s - %s", state.PackageName, state.InstanceID, err)
			errors = append(errors, err)
		}
	}

	if len(errors) == 0 {
		log.Infof("All changes applied.")
		return nil
	}
	return fmt.Errorf("Some actions failed: %v", errors)
}

func buildActionPlan(desired []PackageState, existing []PackageState) (toDeploy []PackageState, toDelete []PackageState) {
	// Figure out what needs to be installed or updated.
	for _, d := range desired {
		alreadyGood := false
		for _, e := range existing {
			if e.PackageName == d.PackageName {
				alreadyGood = e.InstanceID == d.InstanceID
				break
			}
		}
		if !alreadyGood {
			toDeploy = append(toDeploy, d)
		}
	}

	// Figure out what needs to be removed.
	for _, e := range existing {
		keep := false
		for _, d := range desired {
			if e.PackageName == d.PackageName {
				keep = true
				break
			}
		}
		if !keep {
			toDelete = append(toDelete, e)
		}
	}

	return
}
