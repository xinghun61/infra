// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"infra/libs/logging"
)

// FetchInstanceOptions contains parameters for FetchInstance function.
type FetchInstanceOptions struct {
	// ServiceURL is root URL of the backend service, or "" to use default service.
	ServiceURL string
	// Client is http.Client to use to make requests, default is http.DefaultClient.
	Client *http.Client
	// Log is a logger to use for logs, default is logging.DefaultLogger.
	Log logging.Logger

	// PackageName is a name of the package to fetch.
	PackageName string
	// InstanceID identifies an instance of the package to fetch.
	InstanceID string
	// Output is where to write the fetched data to. Must be nil when used with FetchAndDeployInstance.
	Output io.WriteSeeker
}

// FetchInstance downloads package instance file from the repository.
func FetchInstance(options FetchInstanceOptions) (err error) {
	// Fill in default options.
	if options.ServiceURL == "" {
		options.ServiceURL = DefaultServiceURL()
	}
	if options.Client == nil {
		options.Client = http.DefaultClient
	}
	if options.Log == nil {
		options.Log = logging.DefaultLogger
	}
	log := options.Log
	remote := newRemoteService(options.Client, options.ServiceURL, log)

	// Logs the error before returning it.
	defer func() {
		if err != nil {
			log.Errorf("cipd: failed to fetch %s (%s)", options.PackageName, err)
		}
	}()

	// Grab fetch URL.
	log.Infof("cipd: resolving %s:%s", options.PackageName, options.InstanceID)
	fetchInfo, err := remote.fetchInstance(options.PackageName, options.InstanceID)
	if err != nil {
		return
	}

	// reportProgress print fetch progress, throttling the reports rate.
	var prevProgress int64 = 1000
	var prevReportTs time.Time
	reportProgress := func(read int64, total int64) {
		now := time.Now()
		progress := read * 100 / total
		if progress < prevProgress || read == total || now.Sub(prevReportTs) > 5*time.Second {
			log.Infof("cipd: fetching %s: %d%%", options.InstanceID, progress)
			prevReportTs = now
			prevProgress = progress
		}
	}

	// download is a separate function to be able to use deferred close.
	download := func(out io.WriteSeeker, src io.ReadCloser, totalLen int64) error {
		defer src.Close()
		log.Infof("cipd: fetching %s (%.1f Mb)", options.InstanceID, float32(totalLen)/1024.0/1024.0)
		reportProgress(0, totalLen)
		_, err := io.Copy(out, &readerWithProgress{
			reader:   src,
			callback: func(read int64) { reportProgress(read, totalLen) },
		})
		if err == nil {
			log.Infof("cipd: successfully fetched %s", options.InstanceID)
		}
		return err
	}

	// Download the actual data (several attempts).
	maxAttempts := 10
	for attempt := 0; attempt < maxAttempts; attempt++ {
		// Rewind output to zero offset.
		_, err = options.Output.Seek(0, os.SEEK_SET)
		if err != nil {
			return
		}

		// Send the request.
		log.Infof("cipd: initiating the fetch")
		var req *http.Request
		var resp *http.Response
		req, err = http.NewRequest("GET", fetchInfo.FetchURL, nil)
		if err != nil {
			return
		}
		req.Header.Set("User-Agent", userAgent())
		resp, err = options.Client.Do(req)
		if err != nil {
			return
		}

		// Transient error, retry.
		if resp.StatusCode == 408 || resp.StatusCode >= 500 {
			resp.Body.Close()
			log.Warningf("cipd: transient HTTP error %d while fetching the file", resp.StatusCode)
			continue
		}

		// Fatal error, abort.
		if resp.StatusCode >= 400 {
			resp.Body.Close()
			return fmt.Errorf("Server replied with HTTP code %d", resp.StatusCode)
		}

		// Try to fetch.
		err = download(options.Output, resp.Body, resp.ContentLength)
		if err != nil {
			log.Warningf("cipd: transient error fetching the file: %s", err)
			continue
		}

		// Success.
		err = nil
		return
	}

	err = fmt.Errorf("All %d fetch attempts failed", maxAttempts)
	return
}

// FetchAndDeployInstance fetches the package instance and deploys it into
// a site root. It doesn't check whether the instance is already deployed.
// options.Output field is not used and must be set to nil.
func FetchAndDeployInstance(root string, options FetchInstanceOptions) error {
	// Be paranoid.
	err := ValidatePackageName(options.PackageName)
	if err != nil {
		return err
	}
	err = ValidateInstanceID(options.InstanceID)
	if err != nil {
		return err
	}

	// This field is not supported.
	if options.Output != nil {
		return fmt.Errorf("Passed non-nil Output to FetchAndDeployInstance")
	}

	// Use temp file for storing package file. Delete it when done.
	var instance PackageInstance
	tempPath := filepath.Join(root, siteServiceDir, "tmp")
	err = os.MkdirAll(tempPath, 0777)
	if err != nil {
		return err
	}
	f, err := ioutil.TempFile(tempPath, options.InstanceID)
	if err != nil {
		return err
	}
	defer func() {
		// Instance takes ownership of the file, no need to close it separately.
		if instance == nil {
			f.Close()
		}
		os.Remove(f.Name())
	}()

	// Fetch the package data to the provided storage.
	options.Output = f
	err = FetchInstance(options)
	if err != nil {
		return err
	}

	// Open the instance, verify the instance ID.
	instance, err = OpenInstance(f, options.InstanceID)
	if err != nil {
		return err
	}
	defer instance.Close()

	// Deploy it. 'defer' will take care of removing the temp file if needed.
	_, err = DeployInstance(root, instance)
	return err
}

////////////////////////////////////////////////////////////////////////////////

// readerWithProgress is io.Reader that calls callback whenever something is
// read from it.
type readerWithProgress struct {
	reader   io.Reader
	total    int64
	callback func(total int64)
}

func (r *readerWithProgress) Read(p []byte) (int, error) {
	n, err := r.reader.Read(p)
	r.total += int64(n)
	r.callback(r.total)
	return n, err
}
