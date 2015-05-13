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

	"infra/tools/cipd/common"
)

// remoteMaxRetries is how many times to retry transient HTTP errors.
const remoteMaxRetries = 10

type packageInstanceMsg struct {
	PackageName  string `json:"package_name"`
	InstanceID   string `json:"instance_id"`
	RegisteredBy string `json:"registered_by"`
	RegisteredTs string `json:"registered_ts"`
}

// roleChangeMsg corresponds to RoleChange proto message on backend.
type roleChangeMsg struct {
	Action    string `json:"action"`
	Role      string `json:"role"`
	Principal string `json:"principal"`
}

// pendingProcessingError is returned by attachTags if package instance is not
// yet ready and the call should be retried later.
type pendingProcessingError struct {
	message string
}

func (e *pendingProcessingError) Error() string {
	return e.message
}

// remoteImpl implements remote on top of real HTTP calls.
type remoteImpl struct {
	client *Client
}

func isTemporaryNetError(err error) bool {
	// TODO(vadimsh): Figure out how to recognize dial timeouts, read timeouts,
	// etc. For now all errors that end up here are considered temporary.
	return true
}

// isTemporaryHTTPError returns true for HTTP status codes that indicate
// a temporary error that may go away if request is retried.
func isTemporaryHTTPError(statusCode int) bool {
	return statusCode >= 500 || statusCode == 408 || statusCode == 429
}

// makeRequest sends POST or GET REST JSON requests with retries.
func (r *remoteImpl) makeRequest(path, method string, request, response interface{}) error {
	var body []byte
	if request != nil {
		b, err := json.Marshal(request)
		if err != nil {
			return err
		}
		body = b
	}

	url := fmt.Sprintf("%s/_ah/api/%s", r.client.ServiceURL, path)
	for attempt := 0; attempt < remoteMaxRetries; attempt++ {
		if attempt != 0 {
			r.client.Log.Warningf("cipd: retrying request to %s", url)
			r.client.clock.sleep(2 * time.Second)
		}

		// Prepare request.
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
		req.Header.Set("User-Agent", r.client.UserAgent)

		// Connect, read response.
		r.client.Log.Debugf("cipd: %s %s", method, url)
		resp, err := r.client.doAuthenticatedHTTPRequest(req)
		if err != nil {
			if isTemporaryNetError(err) {
				r.client.Log.Warningf("cipd: connectivity error (%s)", err)
				continue
			}
			return err
		}
		responseBody, err := ioutil.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			if isTemporaryNetError(err) {
				r.client.Log.Warningf("cipd: temporary error when reading response (%s)", err)
				continue
			}
			return err
		}
		r.client.Log.Debugf("cipd: http %d: %s", resp.StatusCode, body)
		if isTemporaryHTTPError(resp.StatusCode) {
			continue
		}

		// Success?
		if resp.StatusCode < 300 {
			return json.Unmarshal(responseBody, response)
		}

		// Fatal error?
		if resp.StatusCode == 403 || resp.StatusCode == 401 {
			return ErrAccessDenined
		}
		return fmt.Errorf("Unexpected reply (HTTP %d):\n%s", resp.StatusCode, string(body))
	}

	return ErrBackendInaccessible
}

func (r *remoteImpl) initiateUpload(sha1 string) (s *UploadSession, err error) {
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
		s = &UploadSession{reply.UploadSessionID, reply.UploadURL}
	case "ERROR":
		err = fmt.Errorf("Server replied with error: %s", reply.ErrorMessage)
	default:
		err = fmt.Errorf("Unexpected status: %s", reply.Status)
	}
	return
}

func (r *remoteImpl) finalizeUpload(sessionID string) (finished bool, err error) {
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
		err = ErrUploadSessionDied
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

func (r *remoteImpl) registerInstance(pin common.Pin) (*registerInstanceResponse, error) {
	endpoint, err := instanceEndpoint(pin)
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
		ts, err := convertTimestamp(reply.Instance.RegisteredTs)
		if err != nil {
			return nil, err
		}
		return &registerInstanceResponse{
			alreadyRegistered: reply.Status == "ALREADY_REGISTERED",
			registeredBy:      reply.Instance.RegisteredBy,
			registeredTs:      ts,
		}, nil
	case "UPLOAD_FIRST":
		if reply.UploadSessionID == "" {
			return nil, ErrNoUploadSessionID
		}
		return &registerInstanceResponse{
			uploadSession: &UploadSession{reply.UploadSessionID, reply.UploadURL},
		}, nil
	case "ERROR":
		return nil, errors.New(reply.ErrorMessage)
	}
	return nil, fmt.Errorf("Unexpected register package status: %s", reply.Status)
}

func (r *remoteImpl) fetchInstance(pin common.Pin) (*fetchInstanceResponse, error) {
	endpoint, err := instanceEndpoint(pin)
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
		ts, err := convertTimestamp(reply.Instance.RegisteredTs)
		if err != nil {
			return nil, err
		}
		return &fetchInstanceResponse{
			fetchURL:     reply.FetchURL,
			registeredBy: reply.Instance.RegisteredBy,
			registeredTs: ts,
		}, nil
	case "PACKAGE_NOT_FOUND":
		return nil, fmt.Errorf("Package '%s' is not registered or you do not have permission to fetch it", pin.PackageName)
	case "INSTANCE_NOT_FOUND":
		return nil, fmt.Errorf("Package '%s' doesn't have instance '%s'", pin.PackageName, pin.InstanceID)
	case "ERROR":
		return nil, errors.New(reply.ErrorMessage)
	}
	return nil, fmt.Errorf("Unexpected reply status: %s", reply.Status)
}

func (r *remoteImpl) fetchACL(packagePath string) ([]PackageACL, error) {
	endpoint, err := aclEndpoint(packagePath)
	if err != nil {
		return nil, err
	}
	var reply struct {
		Status       string `json:"status"`
		ErrorMessage string `json:"error_message"`
		Acls         struct {
			Acls []struct {
				PackagePath string   `json:"package_path"`
				Role        string   `json:"role"`
				Principals  []string `json:"principals"`
				ModifiedBy  string   `json:"modified_by"`
				ModifiedTs  string   `json:"modified_ts"`
			} `json:"acls"`
		} `json:"acls"`
	}
	err = r.makeRequest(endpoint, "GET", nil, &reply)
	if err != nil {
		return nil, err
	}
	switch reply.Status {
	case "SUCCESS":
		out := []PackageACL{}
		for _, acl := range reply.Acls.Acls {
			ts, err := convertTimestamp(acl.ModifiedTs)
			if err != nil {
				return nil, err
			}
			out = append(out, PackageACL{
				PackagePath: acl.PackagePath,
				Role:        acl.Role,
				Principals:  acl.Principals,
				ModifiedBy:  acl.ModifiedBy,
				ModifiedTs:  ts,
			})
		}
		return out, nil
	case "ERROR":
		return nil, errors.New(reply.ErrorMessage)
	}
	return nil, fmt.Errorf("Unexpected reply status: %s", reply.Status)
}

func (r *remoteImpl) modifyACL(packagePath string, changes []PackageACLChange) error {
	endpoint, err := aclEndpoint(packagePath)
	if err != nil {
		return err
	}
	var request struct {
		Changes []roleChangeMsg `json:"changes"`
	}
	for _, c := range changes {
		action := ""
		if c.Action == GrantRole {
			action = "GRANT"
		} else if c.Action == RevokeRole {
			action = "REVOKE"
		} else {
			return fmt.Errorf("Unexpected action: %s", action)
		}
		request.Changes = append(request.Changes, roleChangeMsg{
			Action:    action,
			Role:      c.Role,
			Principal: c.Principal,
		})
	}
	var reply struct {
		Status       string `json:"status"`
		ErrorMessage string `json:"error_message"`
	}
	err = r.makeRequest(endpoint, "POST", &request, &reply)
	if err != nil {
		return err
	}
	switch reply.Status {
	case "SUCCESS":
		return nil
	case "ERROR":
		return errors.New(reply.ErrorMessage)
	}
	return fmt.Errorf("Unexpected reply status: %s", reply.Status)
}

func (r *remoteImpl) attachTags(pin common.Pin, tags []string) error {
	// Tags will be passed in the request body, not via URL.
	endpoint, err := tagsEndpoint(pin, nil)
	if err != nil {
		return err
	}
	for _, tag := range tags {
		err = common.ValidateInstanceTag(tag)
		if err != nil {
			return err
		}
	}

	var request struct {
		Tags []string `json:"tags"`
	}
	request.Tags = tags

	var reply struct {
		Status       string `json:"status"`
		ErrorMessage string `json:"error_message"`
	}
	err = r.makeRequest(endpoint, "POST", &request, &reply)
	if err != nil {
		return err
	}
	switch reply.Status {
	case "SUCCESS":
		return nil
	case "PROCESSING_NOT_FINISHED_YET":
		return &pendingProcessingError{reply.ErrorMessage}
	case "ERROR", "PROCESSING_FAILED":
		return errors.New(reply.ErrorMessage)
	}
	return fmt.Errorf("Unexpected status when attaching tags: %s", reply.Status)
}

////////////////////////////////////////////////////////////////////////////////

func instanceEndpoint(pin common.Pin) (string, error) {
	err := common.ValidatePin(pin)
	if err != nil {
		return "", err
	}
	params := url.Values{}
	params.Add("package_name", pin.PackageName)
	params.Add("instance_id", pin.InstanceID)
	return "repo/v1/instance?" + params.Encode(), nil
}

func aclEndpoint(packagePath string) (string, error) {
	err := common.ValidatePackageName(packagePath)
	if err != nil {
		return "", err
	}
	params := url.Values{}
	params.Add("package_path", packagePath)
	return "repo/v1/acl?" + params.Encode(), nil
}

func tagsEndpoint(pin common.Pin, tags []string) (string, error) {
	err := common.ValidatePin(pin)
	if err != nil {
		return "", err
	}
	for _, tag := range tags {
		err = common.ValidateInstanceTag(tag)
		if err != nil {
			return "", err
		}
	}
	params := url.Values{}
	params.Add("package_name", pin.PackageName)
	params.Add("instance_id", pin.InstanceID)
	for _, tag := range tags {
		params.Add("tag", tag)
	}
	return "repo/v1/tags?" + params.Encode(), nil
}

// convertTimestamp coverts string with int64 timestamp in microseconds since
// to time.Time
func convertTimestamp(ts string) (time.Time, error) {
	i, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return time.Time{}, fmt.Errorf("Unexpected timestamp value '%s' in the server response", ts)
	}
	return time.Unix(0, i*1000), nil
}
