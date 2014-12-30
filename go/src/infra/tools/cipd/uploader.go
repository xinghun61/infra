// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"time"

	"infra/libs/logging"
)

var (
	// ErrFinalizationTimeout is returned if CAS service can not finalize upload fast enough.
	ErrFinalizationTimeout = errors.New("Timeout while waiting for CAS service to finalize the upload")
)

// CommonOptions contains upload related parameters shared by UploadToCAS and
// RegisterPackage functions.
type CommonOptions struct {
	// ServiceURL is root URL of the backend service, or "" to use default service.
	ServiceURL string
	// FinalizationTimeout is how long to wait for CAS service to finalize the upload, default is 1 min.
	FinalizationTimeout time.Duration
	// Client is http.Client to use to make requests, default is http.DefaultClient.
	Client *http.Client
	// Log is a logger to use for logs, default is logging.DefaultLogger.
	Log logging.Logger
}

// UploadToCASOptions contains parameters for UploadToCAS function.
type UploadToCASOptions struct {
	CommonOptions

	// SHA1 is a SHA1 hash of data to upload, usually package's InstanceID().
	SHA1 string
	// Data provides actual data to upload. It is seekable to support resumable uploads.
	Data io.ReadSeeker
	// UploadSessionID identified existing upload session. Empty string to start a new one.
	UploadSessionID string
	// UploadURL is where to upload the file to. Must be set if UploadSessionID is not empty.
	UploadURL string
}

// UploadToCAS uploads package data blob (and only data blob, no signatures or
// metadata) to Content Addressed Store if it is not there already. The data is
// addressed by SHA1 hash (also known as package's InstanceID). It can be used
// as a standalone function (if UploadSessionID is "") or as a part of more high
// level upload process (in that case upload session can be opened elsewhere and
// its properties passed here via UploadSessionID and UploadURL). Returns nil on
// successful upload.
func UploadToCAS(options UploadToCASOptions) error {
	// Fill in default options.
	if options.ServiceURL == "" {
		options.ServiceURL = DefaultServiceURL()
	}
	if options.FinalizationTimeout == 0 {
		options.FinalizationTimeout = 60 * time.Second
	}
	if options.Client == nil {
		options.Client = http.DefaultClient
	}
	if options.Log == nil {
		options.Log = logging.DefaultLogger
	}
	log := options.Log
	remote := newRemoteService(options.Client, options.ServiceURL, log)

	// Open new upload session if existing is not provided.
	var session *uploadSession
	var err error
	if options.UploadSessionID == "" {
		log.Infof("cipd: uploading %s: initiating", options.SHA1)
		session, err = remote.initiateUpload(options.SHA1)
		if err != nil {
			log.Warningf("cipd: can't upload %s - %s", options.SHA1, err)
			return err
		}
		if session == nil {
			log.Infof("cipd: %s is already uploaded", options.SHA1)
			return nil
		}
	} else {
		if options.UploadURL == "" {
			return errors.New("UploadURL must be set if UploadSessionID is used")
		}
		session = &uploadSession{
			ID:  options.UploadSessionID,
			URL: options.UploadURL,
		}
	}

	// Upload the file to CAS storage.
	err = resumableUpload(session.URL, 8*1024*1024, options)
	if err != nil {
		return err
	}

	// Finalize the upload, wait until server verifies and publishes the file.
	started := clock.Now()
	delay := time.Second
	for {
		published, err := remote.finalizeUpload(session.ID)
		if published {
			log.Infof("cipd: successfully uploaded %s", options.SHA1)
			return nil
		}
		if err != nil {
			log.Warningf("cipd: upload of %s failed: %s", options.SHA1, err)
			return err
		}
		if clock.Now().Sub(started) > options.FinalizationTimeout {
			log.Warningf("cipd: upload of %s failed: timeout", options.SHA1)
			return ErrFinalizationTimeout
		}
		log.Infof("cipd: uploading %s: verifying", options.SHA1)
		clock.Sleep(delay)
		if delay < 4*time.Second {
			delay += 500 * time.Millisecond
		}
	}
}

// RegisterPackageOptions contains parameters for RegisterPackage function.
type RegisterPackageOptions struct {
	CommonOptions

	// Package is a package to upload.
	Package Package
	// Metadata describes when and how the package was built.
	Metadata Metadata
}

// RegisterPackage makes the package instance available for clients by
// uploading it to the storage (along with metadata and signatures) and
// registering it in the package repository.
func RegisterPackage(options RegisterPackageOptions) error {
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
	newRemoteService(options.Client, options.ServiceURL, log)

	// TODO(vadimsh): Implement.

	return nil
}

////////////////////////////////////////////////////////////////////////////////
// Wrapper around Cloud Endpoints APIs exposed by backend.
// See //appengine/chrome_infra_packages.

type remoteService struct {
	client     *http.Client
	serviceURL string
	log        logging.Logger
}

type uploadSession struct {
	ID  string
	URL string
}

// newRemoteService is mocked in tests.
var newRemoteService = func(client *http.Client, url string, log logging.Logger) *remoteService {
	return &remoteService{
		client:     client,
		serviceURL: url,
		log:        log,
	}
}

// makeRequest sends POST request with retries.
func (r *remoteService) makeRequest(path string, response interface{}) error {
	url := fmt.Sprintf("%s/_ah/api/%s", r.serviceURL, path)
	for attempt := 0; attempt < 10; attempt++ {
		if attempt != 0 {
			r.log.Warningf("cipd: retrying request to %s", url)
			clock.Sleep(2 * time.Second)
		}
		req, err := http.NewRequest("POST", url, nil)
		if err != nil {
			return err
		}
		req.Header.Set("User-Agent", userAgent())
		resp, err := r.client.Do(req)
		if err != nil {
			return err
		}
		// Success?
		if resp.StatusCode < 300 {
			defer resp.Body.Close()
			return json.NewDecoder(resp.Body).Decode(response)
		}
		// Fatal error?
		if resp.StatusCode >= 300 && resp.StatusCode < 500 {
			defer resp.Body.Close()
			body, _ := ioutil.ReadAll(resp.Body)
			return fmt.Errorf("Unexpected reply (HTTP %d):\n%s", resp.StatusCode, string(body))
		}
		// Retry.
		resp.Body.Close()
	}
	return fmt.Errorf("Request to %s failed after 10 attempts", url)
}

func (r *remoteService) initiateUpload(sha1 string) (s *uploadSession, err error) {
	var reply struct {
		Status          string `json:"status"`
		UploadSessionID string `json:"upload_session_id"`
		UploadURL       string `json:"upload_url"`
		ErrorMessage    string `json:"error_message"`
	}
	err = r.makeRequest("cas/v1/upload/SHA1/"+sha1, &reply)
	if err != nil {
		return
	}
	switch reply.Status {
	case "ALREADY_UPLOADED":
		return
	case "SUCCESS":
		s = &uploadSession{
			ID:  reply.UploadSessionID,
			URL: reply.UploadURL,
		}
	case "ERROR":
		err = fmt.Errorf("Server replied with error: %s", reply.ErrorMessage)
	default:
		err = fmt.Errorf("Unexpected status: %s", reply.Status)
	}
	return
}

func (r *remoteService) finalizeUpload(sessionID string) (finished bool, err error) {
	var reply struct {
		Status       string `json:"status"`
		ErrorMessage string `json:"error_message"`
	}
	err = r.makeRequest("cas/v1/finalize/"+sessionID, &reply)
	if err != nil {
		return
	}
	switch reply.Status {
	case "MISSING":
		err = errors.New("Upload session is unexpectedly missing")
	case "UPLOADING":
	case "VERIFYING":
		finished = false
	case "PUBLISHED":
		finished = true
	case "ERROR":
		err = errors.New(reply.ErrorMessage)
	default:
		err = fmt.Errorf("Unexpected upload session status: %s", reply.Status)
	}
	return
}

////////////////////////////////////////////////////////////////////////////////
// Google Storage resumable upload protocol.
// See https://cloud.google.com/storage/docs/concepts-techniques#resumable

// errTransientError is returned by getNextOffset in case of retryable error.
var errTransientError = errors.New("Transient error in getUploadedOffset")

// resumableUpload is mocked in tests.
var resumableUpload = func(uploadURL string, chunkSize int64, opts UploadToCASOptions) error {
	// Grab the total length of the file.
	length, err := opts.Data.Seek(0, os.SEEK_END)
	if err != nil {
		return err
	}
	_, err = opts.Data.Seek(0, os.SEEK_SET)
	if err != nil {
		return err
	}

	// Called when some new data is uploaded.
	reportProgress := func(offset int64) {
		if length != 0 {
			opts.Log.Infof("cipd: uploading %s: %d%%", opts.SHA1, offset*100/length)
		}
	}

	// Called when transient error happens.
	reportTransientError := func() {
		opts.Log.Warningf("cipd: transient upload error, retrying...")
		clock.Sleep(2 * time.Second)
	}

	var offset int64
	reportProgress(0)
	for {
		// Grab latest uploaded offset if not known.
		if offset == -1 {
			offset, err = getNextOffset(uploadURL, length, opts.Client)
			if err == errTransientError {
				offset = -1
				reportTransientError()
				continue
			}
			if err != nil {
				return err
			}
			reportProgress(offset)
			if offset == length {
				return nil
			}
			opts.Log.Warningf("cipd: resuming upload from offset %d", offset)
		}

		// Length of a chunk to upload.
		var chunk int64 = chunkSize
		if chunk > length-offset {
			chunk = length - offset
		}

		// Upload the chunk.
		opts.Data.Seek(offset, os.SEEK_SET)
		r, err := http.NewRequest("PUT", uploadURL, io.LimitReader(opts.Data, chunk))
		if err != nil {
			return err
		}
		rangeHeader := fmt.Sprintf("bytes %d-%d/%d", offset, offset+chunk-1, length)
		r.Header.Set("Content-Range", rangeHeader)
		r.Header.Set("Content-Length", fmt.Sprintf("%d", chunk))
		r.Header.Set("User-Agent", userAgent())
		resp, err := opts.Client.Do(r)
		if err != nil {
			return err
		}
		resp.Body.Close()

		// Partially or fully uploaded.
		if resp.StatusCode == 308 || resp.StatusCode == 200 {
			offset += chunk
			reportProgress(offset)
			if offset == length {
				return nil
			}
		} else if resp.StatusCode < 500 && resp.StatusCode != 408 {
			return fmt.Errorf("Unexpected response during file upload: HTTP %d", resp.StatusCode)
		} else {
			// Transient error. Need to query for latest uploaded offset to resume.
			offset = -1
			reportTransientError()
		}
	}
}

// getNextOffset queries the storage for size of persisted data.
func getNextOffset(uploadURL string, length int64, client *http.Client) (offset int64, err error) {
	r, err := http.NewRequest("PUT", uploadURL, nil)
	if err != nil {
		return
	}
	r.Header.Set("Content-Range", fmt.Sprintf("bytes */%d", length))
	r.Header.Set("Content-Length", "0")
	r.Header.Set("User-Agent", userAgent())
	resp, err := client.Do(r)
	if err != nil {
		return
	}
	resp.Body.Close()

	if resp.StatusCode == 200 {
		// Fully uploaded.
		offset = length
	} else if resp.StatusCode == 308 {
		// Partially uploaded, extract last uploaded offset from Range header.
		rangeHeader := resp.Header.Get("Range")
		if rangeHeader != "" {
			_, err = fmt.Sscanf(rangeHeader, "bytes=0-%d", &offset)
			if err == nil {
				// |offset| is an *offset* of a last uploaded byte, not the data length.
				offset++
			}
		}
	} else if resp.StatusCode < 500 && resp.StatusCode != 408 {
		err = fmt.Errorf("Unexpected response (HTTP %d) when querying for uploaded offset", resp.StatusCode)
	} else {
		err = errTransientError
	}
	return
}

////////////////////////////////////////////////////////////////////////////////
// Mockable clock.

var clock clockInterface = &realClock{}

type clockInterface interface {
	Now() time.Time
	Sleep(time.Duration)
}

type realClock struct{}

func (c *realClock) Now() time.Time        { return time.Now() }
func (c *realClock) Sleep(d time.Duration) { time.Sleep(d) }
