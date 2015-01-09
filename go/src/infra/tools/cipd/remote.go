// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"infra/libs/logging"
)

// remoteService is a wrapper around Cloud Endpoints APIs exposed by backend.
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

// packageInstanceMsg corresponds to PackageInstance message on the backend.
type packageInstanceMsg struct {
	PackageName  string `json:"package_name"`
	InstanceID   string `json:"instance_id"`
	RegisteredBy string `json:"registered_by"`
	RegisteredTs string `json:"registered_ts"`
}

// packageInstance is almost like packageInstanceMsg, but with timestamp as
// time.Time. See also makePackageInstanceInfo.
type packageInstanceInfo struct {
	PackageName  string
	InstanceID   string
	RegisteredBy string
	RegisteredTs time.Time
}

type registerInstanceResponse struct {
	UploadSession     *uploadSession
	AlreadyRegistered bool
	Info              packageInstanceInfo
}

type fetchInstanceResponse struct {
	FetchURL string
	Info     packageInstanceInfo
}

// newRemoteService is mocked in tests.
var newRemoteService = func(client *http.Client, url string, log logging.Logger) *remoteService {
	return &remoteService{
		client:     client,
		serviceURL: url,
		log:        log,
	}
}

// makeRequest sends POST or GET request with retries.
func (r *remoteService) makeRequest(path, method string, request, response interface{}) error {
	var body []byte
	var err error
	if request != nil {
		body, err = json.Marshal(request)
		if err != nil {
			return err
		}
	}
	url := fmt.Sprintf("%s/_ah/api/%s", r.serviceURL, path)
	for attempt := 0; attempt < 10; attempt++ {
		if attempt != 0 {
			r.log.Warningf("cipd: retrying request to %s", url)
			clock.Sleep(2 * time.Second)
		}
		var bodyReader io.Reader
		if body != nil {
			bodyReader = bytes.NewReader(body)
		}
		req, err := http.NewRequest(method, url, bodyReader)
		if err != nil {
			return err
		}
		if body != nil {
			req.Header.Set("Content-Type", "application/json")
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
	err = r.makeRequest("cas/v1/upload/SHA1/"+sha1, "POST", nil, &reply)
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
	err = r.makeRequest("cas/v1/finalize/"+sessionID, "POST", nil, &reply)
	if err != nil {
		return
	}
	switch reply.Status {
	case "MISSING":
		err = errors.New("Upload session is unexpectedly missing")
	case "UPLOADING", "VERIFYING":
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

func (r *remoteService) registerInstance(packageName, instanceID string) (*registerInstanceResponse, error) {
	endpoint, err := instanceEndpoint(packageName, instanceID)
	if err != nil {
		return nil, err
	}
	var reply struct {
		Status          string             `json:"status"`
		Instance        packageInstanceMsg `json:"instance"`
		UploadSessionID string             `json:"upload_session_id"`
		UploadURL       string             `json:"upload_url"`
		ErrorMessage    string             `json:"error_message"`
	}
	err = r.makeRequest(endpoint, "POST", nil, &reply)
	if err != nil {
		return nil, err
	}
	switch reply.Status {
	case "REGISTERED", "ALREADY_REGISTERED":
		info, err := makePackageInstanceInfo(reply.Instance)
		if err != nil {
			return nil, err
		}
		return &registerInstanceResponse{
			AlreadyRegistered: reply.Status == "ALREADY_REGISTERED",
			Info:              info,
		}, nil
	case "UPLOAD_FIRST":
		if reply.UploadSessionID == "" {
			return nil, errors.New("Server didn't provide upload session ID")
		}
		return &registerInstanceResponse{
			UploadSession: &uploadSession{
				ID:  reply.UploadSessionID,
				URL: reply.UploadURL,
			},
		}, nil
	case "ERROR":
		return nil, errors.New(reply.ErrorMessage)
	}
	return nil, fmt.Errorf("Unexpected register package status: %s", reply.Status)
}

func (r *remoteService) fetchInstance(packageName, instanceID string) (*fetchInstanceResponse, error) {
	endpoint, err := instanceEndpoint(packageName, instanceID)
	if err != nil {
		return nil, err
	}
	var reply struct {
		Status       string             `json:"status"`
		Instance     packageInstanceMsg `json:"instance"`
		FetchURL     string             `json:"fetch_url"`
		ErrorMessage string             `json:"error_message"`
	}
	err = r.makeRequest(endpoint, "GET", nil, &reply)
	if err != nil {
		return nil, err
	}
	switch reply.Status {
	case "SUCCESS":
		info, err := makePackageInstanceInfo(reply.Instance)
		if err != nil {
			return nil, err
		}
		return &fetchInstanceResponse{
			FetchURL: reply.FetchURL,
			Info:     info,
		}, nil
	case "PACKAGE_NOT_FOUND":
		return nil, fmt.Errorf("Package '%s' is not registered or you do not have permission to fetch it", packageName)
	case "INSTANCE_NOT_FOUND":
		return nil, fmt.Errorf("Package '%s' doesn't have instance '%s'", packageName, instanceID)
	case "ERROR":
		return nil, errors.New(reply.ErrorMessage)
	}
	return nil, fmt.Errorf("Unexpected reply status: %s", reply.Status)
}

////////////////////////////////////////////////////////////////////////////////

func instanceEndpoint(packageName, instanceID string) (string, error) {
	err := ValidatePackageName(packageName)
	if err != nil {
		return "", err
	}
	err = ValidateInstanceID(instanceID)
	if err != nil {
		return "", err
	}
	params := url.Values{}
	params.Add("package_name", packageName)
	params.Add("instance_id", instanceID)
	return "repo/v1/instance?" + params.Encode(), nil
}

func makePackageInstanceInfo(msg packageInstanceMsg) (pi packageInstanceInfo, err error) {
	// String with int64 timestamp in microseconds since epoch -> time.Time.
	ts, err := strconv.ParseInt(msg.RegisteredTs, 10, 64)
	if err != nil {
		err = fmt.Errorf("Unexpected timestamp value '%s' in the server response", msg.RegisteredTs)
		return
	}
	pi = packageInstanceInfo{
		PackageName:  msg.PackageName,
		InstanceID:   msg.InstanceID,
		RegisteredBy: msg.RegisteredBy,
		RegisteredTs: time.Unix(0, ts*1000),
	}
	return
}
