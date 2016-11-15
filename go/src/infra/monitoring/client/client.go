// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"bytes"
	"encoding/json"
	"expvar"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"infra/monitoring/messages"
)

const (
	maxRetries = 3
	// FYI https://github.com/golang/go/issues/9405 in Go 1.4
	// http timeout errors are logged as "use of closed network connection"
	timeout = 5 * time.Second

	chromeBuildExtractURL = "https://chrome-build-extract.appspot.com"
)

var (
	errLog  = log.New(os.Stderr, "", log.Lshortfile|log.Ltime)
	infoLog = log.New(os.Stdout, "", log.Lshortfile|log.Ltime)
	expvars = expvar.NewMap("client")
)

// BuilderURL returns the builder URL for the given master and builder.
func BuilderURL(master *messages.MasterLocation, builder string) *url.URL {
	newURL := master.URL
	newURL.Path += fmt.Sprintf("/builders/%s", builder)
	return &newURL
}

// BuildURL returns the build URL for the given master, builder and build number.
func BuildURL(master *messages.MasterLocation, builder string, buildNum int64) *url.URL {
	newURL := master.URL
	newURL.Path += fmt.Sprintf("/builders/%s/builds/%d", builder, buildNum)
	return &newURL
}

// StepURL returns the step URL for the given master, builder, step and build number.
func StepURL(master *messages.MasterLocation, builder, step string, buildNum int64) *url.URL {
	newURL := master.URL
	newURL.Path += fmt.Sprintf("/builders/%s/builds/%d/steps/%s",
		builder, buildNum, step)
	return &newURL
}

// Reader provides access to read status information from various parts of chrome
// developer infrastructure.
type Reader interface {
	// Build fetches the build summary for master, builder and buildNum
	// from build.chromium.org.
	Build(master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error)

	// LatestBuilds fetches a list of recent build summaries for master and builder
	// from build.chromium.org.
	LatestBuilds(master *messages.MasterLocation, build string) ([]*messages.Build, error)

	// TestResults fetches the results of a step failure's test run.
	TestResults(masterName *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error)

	// BuildExtract fetches build information for master from CBE.
	BuildExtract(master *messages.MasterLocation) (*messages.BuildExtract, error)

	// StdioForStep fetches the standard output for a given build step, and an error if any
	// occurred.
	StdioForStep(master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error)

	// CrbugItems fetches a list of open issues from crbug matching the given label.
	CrbugItems(label string) ([]messages.CrbugItem, error)

	// Findit fetches items from the findit service, which identifies possible culprit CLs for a failed build.
	Findit(master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error)
}

// Writer writes out data to other services, most notably sheriff-o-matic.
type Writer interface {
	// PostAlerts posts alerts to Sheriff-o-Matic.
	PostAlerts(alerts *messages.AlertsSummary) error
}

type trackingHTTPClient struct {
	c *http.Client
	// Some counters for reporting. Only modify through synchronized methods.
	// TODO: add some more detailed stats about response times so we can
	// track and alert on those too.
	totalReqs  int64
	totalErrs  int64
	totalBytes int64
	currReqs   int64
}

type reader struct {
	hc *trackingHTTPClient
	// bCache is a map of build cache key to Build message.
	bCache map[string]*messages.Build
	// bLock protects bCache
	bLock sync.Mutex
}

type writer struct {
	hc         *trackingHTTPClient
	alertsBase string
}

// NewReader returns a new Reader, which will read data from various chrome infra
// data sources.
func NewReader() Reader {
	return &reader{
		hc: &trackingHTTPClient{
			c: http.DefaultClient,
		},
		bCache: map[string]*messages.Build{},
	}
}

func cacheKeyForBuild(master *messages.MasterLocation, builder string, number int64) string {
	return filepath.FromSlash(
		fmt.Sprintf("%s/%s/%d.json", url.QueryEscape(master.String()), url.QueryEscape(builder), number))
}

func (r *reader) Build(master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	// TODO: get this from cache.
	r.bLock.Lock()
	build, ok := r.bCache[cacheKeyForBuild(master, builder, buildNum)]
	r.bLock.Unlock()
	if ok {
		return build, nil
	}

	build = &messages.Build{}
	URL := fmt.Sprintf("%s/p/%s/builders/%s/builds/%d?json=1",
		chromeBuildExtractURL, master.Name(), builder, buildNum)

	expvars.Add("Build", 1)
	defer expvars.Add("Build", -1)
	code, err := r.hc.getJSON(URL, build)

	if code == 404 {
		// FIXME: Don't directly poll so many builders.
		expvars.Add("DirectPoll", 1)
		defer expvars.Add("DirectPoll", -1)
		URL = fmt.Sprintf("%s/json/builders/%s/builds/%d",
			master, builder, buildNum)
		if code, err := r.hc.getJSON(URL, build); err != nil {
			errLog.Printf("Error (%d) fetching %s: %v", code, master.String(), err)
			return nil, err
		}
		return build, nil
	}

	if err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return build, nil
}

func (r *reader) LatestBuilds(master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	v := url.Values{}
	v.Add("master", master.Name())
	v.Add("builder", builder)

	URL := fmt.Sprintf("%s/get_builds?%s", chromeBuildExtractURL, v.Encode())
	res := struct {
		Builds []*messages.Build `json:"builds"`
	}{}

	expvars.Add("LatestBuilds", 1)
	defer expvars.Add("LatestBuilds", -1)
	if code, err := r.hc.getJSON(URL, &res); err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	r.bLock.Lock()
	for _, b := range res.Builds {
		if cacheable(b) {
			r.bCache[cacheKeyForBuild(master, builder, b.Number)] = b
		}
	}
	r.bLock.Unlock()

	return res.Builds, nil
}

func (r *reader) TestResults(master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	v := url.Values{}
	v.Add("name", "full_results.json")
	v.Add("master", master.Name())
	v.Add("builder", builderName)
	v.Add("buildnumber", fmt.Sprintf("%d", buildNumber))
	v.Add("testtype", stepName)

	URL := fmt.Sprintf("https://test-results.appspot.com/testfile?%s", v.Encode())
	tr := &messages.TestResults{}

	expvars.Add("TestResults", 1)
	defer expvars.Add("TestResults", -1)
	if code, err := r.hc.getJSON(URL, tr); err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return tr, nil
}

func (r *reader) BuildExtract(masterURL *messages.MasterLocation) (*messages.BuildExtract, error) {
	URL := fmt.Sprintf("%s/get_master/%s", chromeBuildExtractURL, masterURL.Name())
	ret := &messages.BuildExtract{}

	expvars.Add("BuildExtract", 1)
	defer expvars.Add("BuildExtract", -1)
	code, err := r.hc.getJSON(URL, ret)

	if code == 404 {
		// FIXME: Don't directly poll so many builders.
		URL = fmt.Sprintf("%s/json", masterURL.String())
		expvars.Add("DirectPoll", 1)
		defer expvars.Add("DirectPoll", -1)
		if code, err := r.hc.getJSON(URL, ret); err != nil {
			errLog.Printf("Error (%d) fetching %s: %v", code, masterURL.String(), err)
			return nil, err
		}
		return ret, nil
	}

	if err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return ret, nil
}

func (r *reader) StdioForStep(master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", master, builder, buildNum, step)

	expvars.Add("StdioForStep", 1)
	defer expvars.Add("StdioForStep", -1)
	res, _, err := r.hc.getText(URL)
	return strings.Split(res, "\n"), err
}

func (r *reader) CrbugItems(label string) ([]messages.CrbugItem, error) {
	v := url.Values{}
	v.Add("can", "open")
	v.Add("maxResults", "100")
	v.Add("q", fmt.Sprintf("label:%s", label))

	URL := "https://www.googleapis.com/projecthosting/v2/projects/chromium/issues?" + v.Encode()
	expvars.Add("CrbugIssues", 1)
	defer expvars.Add("CrbugIssues", -1)
	res := &messages.CrbugSearchResults{}
	if code, err := r.hc.getJSON(URL, res); err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Items, nil
}

type finditAPIResponse struct {
	Results []*messages.FinditResult `json:"results"`
}

func (r *reader) Findit(master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	data := map[string]interface{}{
		"builds": []map[string]interface{}{
			{
				"master_url":   master.String(),
				"builder_name": builder,
				"build_number": buildNum,
				"failed_steps": failedSteps,
			},
		},
	}

	b := bytes.NewBuffer(nil)
	err := json.NewEncoder(b).Encode(data)

	if err != nil {
		return nil, err
	}

	URL := "https://findit-for-me.appspot.com/_ah/api/findit/v1/buildfailure"
	expvars.Add("Findit", 1)
	defer expvars.Add("Findit", -1)
	res := &finditAPIResponse{}
	if code, err := r.hc.postJSON(URL, b.Bytes(), res); err != nil {
		errLog.Printf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Results, nil
}

func cacheable(b *messages.Build) bool {
	return len(b.Times) > 1 && b.Times[1] != 0
}

// NewWriter returns a new Client, which will post alerts to alertsBase.
func NewWriter(alertsBase string, transport http.RoundTripper) Writer {
	return &writer{hc: &trackingHTTPClient{
		c: &http.Client{
			Transport: transport,
		},
	}, alertsBase: alertsBase}
}

func (w *writer) PostAlerts(alerts *messages.AlertsSummary) error {
	return w.hc.trackRequestStats(func() (length int64, err error) {
		infoLog.Printf("POSTing alerts to %s", w.alertsBase)
		expvars.Add("PostAlerts", 1)
		defer expvars.Add("PostAlerts", -1)
		b, err := json.Marshal(alerts)
		if err != nil {
			return
		}

		resp, err := w.hc.c.Post(w.alertsBase, "application/json", bytes.NewBuffer(b))
		if err != nil {
			return
		}

		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, w.alertsBase)
			return
		}

		defer resp.Body.Close()
		length = resp.ContentLength

		return
	})
}

func (hc *trackingHTTPClient) trackRequestStats(cb func() (int64, error)) error {
	var err error
	expvars.Add("InFlight", 1)
	defer expvars.Add("InFlight", -1)
	defer func() {
		if err != nil {
			expvars.Add("TotalErrors", 1)
		}
	}()
	length := int64(0)
	length, err = cb()
	expvars.Add("TotalBytesRead", length)
	return err
}

func (hc *trackingHTTPClient) attemptJSONGet(url string, v interface{}) (bool, int, int64, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		errLog.Printf("error while creating request: %q, possibly retrying.", err.Error())
		return false, 0, 0, err
	}

	return hc.attemptReq(req, v)
}

func (hc *trackingHTTPClient) attemptReq(r *http.Request, v interface{}) (bool, int, int64, error) {
	r.Header.Set("User-Agent", "Go-http-client/1.1 alerts_dispatcher")
	resp, err := hc.c.Do(r)
	if err != nil {
		errLog.Printf("error: %q, possibly retrying.", err.Error())
		return false, 0, 0, err
	}

	defer resp.Body.Close()
	status := resp.StatusCode
	if status != http.StatusOK {
		return false, status, 0, fmt.Errorf("Bad response code: %v", status)
	}

	if err = json.NewDecoder(resp.Body).Decode(v); err != nil {
		errLog.Printf("Error decoding response: %v", err)
		return false, status, 0, err
	}
	ct := strings.ToLower(resp.Header.Get("Content-Type"))
	expected := "application/json"
	if !strings.HasPrefix(ct, expected) {
		err = fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\": %s", expected, ct, r.URL)
		return false, status, 0, err
	}
	infoLog.Printf("Fetched(%d) json: %s", status, r.URL)

	return true, status, resp.ContentLength, err
}

// postJSON does a simple HTTP POST on a endpoint, with retries and backoff.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) postJSON(url string, data []byte, v interface{}) (status int, err error) {
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	req.Header.Set("User-Agent", "Go-http-client/1.1 alerts_dispatcher")
	req.Header.Set("Content-Type", "application/json")
	if err != nil {
		return 0, err
	}

	err = hc.trackRequestStats(func() (length int64, err error) {
		attempts := 0
		for {
			infoLog.Printf("Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			done, tStatus, length, err := hc.attemptReq(req, v)
			status = tStatus
			if done {
				return length, err
			}
			if err != nil {
				errLog.Printf("Error attempting fetch: %v", err)
			}

			attempts++
			if attempts > maxRetries {
				return 0, fmt.Errorf("Error fetching %s, max retries exceeded.", url)
			}

			if status >= 400 && status < 500 {
				return 0, fmt.Errorf("HTTP status %d, not retrying: %s", status, url)
			}

			time.Sleep(time.Duration(math.Pow(2, float64(attempts))) * time.Second)
		}
	})

	return status, err
}

// getJSON does a simple HTTP GET on a getJSON endpoint.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) getJSON(url string, v interface{}) (status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {
		attempts := 0
		for {
			infoLog.Printf("Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			done, tStatus, length, err := hc.attemptJSONGet(url, v)
			status = tStatus
			if done {
				return length, err
			}
			if err != nil {
				errLog.Printf("Error attempting fetch: %v", err)
			}

			attempts++
			if attempts > maxRetries {
				return 0, fmt.Errorf("Error fetching %s, max retries exceeded.", url)
			}

			if status >= 400 && status < 500 {
				return 0, fmt.Errorf("HTTP status %d, not retrying: %s", status, url)
			}

			time.Sleep(time.Duration(math.Pow(2, float64(attempts))) * time.Second)
		}
	})

	return status, err
}

// getText does a simple HTTP GET on a text endpoint.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) getText(url string) (ret string, status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {

		infoLog.Printf("Fetching text (%d): %s", hc.currReqs, url)
		resp, err := hc.c.Get(url)
		if err != nil {
			err = fmt.Errorf("couldn't resolve %s: %s", url, err)
			return
		}
		defer resp.Body.Close()

		b, err := ioutil.ReadAll(resp.Body)
		status = resp.StatusCode
		if err != nil {
			return
		}

		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, url)
			return
		}

		ret = string(b)
		length = resp.ContentLength

		infoLog.Printf("Fetched(%d) text: %s", resp.StatusCode, url)
		return length, err
	})
	return ret, status, nil
}
