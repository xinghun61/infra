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
	"math"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
	"infra/monitoring/messages"

	"github.com/luci/luci-go/common/logging"
)

type contextKey string

const (
	maxRetries = 3
	// FYI https://github.com/golang/go/issues/9405 in Go 1.4
	// http timeout errors are logged as "use of closed network connection"
	timeout = 5 * time.Second

	chromeBuildExtractURL = "https://chrome-build-extract.appspot.com"
	clientReaderKey       = contextKey("infra-client-reader")
)

var (
	expvars = expvar.NewMap("client")
)

// WithReader returns a context with its reader set to r.
func WithReader(ctx context.Context, r readerType) context.Context {
	return context.WithValue(ctx, clientReaderKey, r)
}

// GetReader returns the current client.Reader for the context, or nil.
func GetReader(ctx context.Context) readerType {
	if reader, ok := ctx.Value(clientReaderKey).(readerType); ok {
		return reader
	}
	return nil
}

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

// readerType provides access to read status information from various parts of chrome
// developer infrastructure. TODO(seanmccullough): Change all of these to start lowercase
// now that the type isn't exported.
type readerType interface {
	Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error)

	LatestBuilds(ctx context.Context, master *messages.MasterLocation, build string) ([]*messages.Build, error)

	TestResults(ctx context.Context, masterName *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error)

	BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error)

	StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error)

	CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error)

	Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error)
}

// Writer writes out data to other services, most notably sheriff-o-matic.
type Writer interface {
	// PostAlerts posts alerts to Sheriff-o-Matic.
	PostAlerts(ctx context.Context, alerts *messages.AlertsSummary) error
}

// Build fetches the build summary for master, builder and buildNum
// from build.chromium.org.
func Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	return GetReader(ctx).Build(ctx, master, builder, buildNum)
}

// LatestBuilds fetches a list of recent build summaries for master and builder
// from build.chromium.org.
func LatestBuilds(ctx context.Context, master *messages.MasterLocation, build string) ([]*messages.Build, error) {
	return GetReader(ctx).LatestBuilds(ctx, master, build)
}

// TestResults fetches the results of a step failure's test run.
func TestResults(ctx context.Context, masterName *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	return GetReader(ctx).TestResults(ctx, masterName, builderName, stepName, buildNumber)
}

// BuildExtract fetches build information for master from CBE.
func BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error) {
	return GetReader(ctx).BuildExtract(ctx, master)
}

// StdioForStep fetches the standard output for a given build step, and an error if any
// occurred.
func StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	return GetReader(ctx).StdioForStep(ctx, master, builder, step, buildNum)
}

// CrbugItems fetches a list of open issues from crbug matching the given label.
func CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error) {
	return GetReader(ctx).CrbugItems(ctx, label)
}

// Findit fetches items from the findit service, which identifies possible culprit CLs for a failed build.
func Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	return GetReader(ctx).Findit(ctx, master, builder, buildNum, failedSteps)
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

	trCache trCache
}

// A cache of the test results /builders endpoint. This endpoints returns JSON
// representing what tests it knows about.
// format is master -> test -> list of builders
type trCache map[string]map[string][]string

type writer struct {
	hc         *trackingHTTPClient
	alertsBase string
}

// BuilderData is the data returned from the GET "/builders"
// endpoint.
// TODO(martinis): Change this to be imported from test results once these
// structs have been refactored out of the frontend package. Can't import them
// now because frontend init() sets up http handlers.
type BuilderData struct {
	Masters           []Master `json:"masters"`
	NoUploadTestTypes []string `json:"no_upload_test_types"`
}

// Master represents information about a build master.
type Master struct {
	Name       string           `json:"name"`
	Identifier string           `json:"url_name"`
	Groups     []string         `json:"groups"`
	Tests      map[string]*Test `json:"tests"`
}

// Test represents information about Tests in a master.
type Test struct {
	Builders []string `json:"builders"`
}

// NewReader returns a new default reader implementation, which will read data from various chrome infra
// data sources.
func NewReader(ctx context.Context) (readerType, error) {
	r := &reader{
		hc: &trackingHTTPClient{
			c: http.DefaultClient,
		},
		bCache:  map[string]*messages.Build{},
		trCache: map[string]map[string][]string{},
	}

	URL := "https://test-results.appspot.com/builders"
	tmpCache := &model.BuilderData{}
	code, err := r.hc.getJSON(ctx, URL, tmpCache)
	if err != nil {
		return nil, err
	}
	if code > 400 {
		return nil, fmt.Errorf("test result cache request failed with code %v", code)
	}

	for _, master := range tmpCache.Masters {
		r.trCache[master.Name] = map[string][]string{}
		for testName, test := range master.Tests {
			r.trCache[master.Name][testName] = test.Builders
		}
	}

	return r, nil
}

func cacheKeyForBuild(master *messages.MasterLocation, builder string, number int64) string {
	return filepath.FromSlash(
		fmt.Sprintf("%s/%s/%d.json", url.QueryEscape(master.String()), url.QueryEscape(builder), number))
}

func (r *reader) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
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
	code, err := r.hc.getJSON(ctx, URL, build)

	// TODO(martiniss): Remove this, and replace with milo access with correct
	// credentials.
	if code == 404 || code == 403 || code == 401 {
		// FIXME: Don't directly poll so many builders.
		expvars.Add("DirectPoll", 1)
		defer expvars.Add("DirectPoll", -1)
		URL = fmt.Sprintf("%s/json/builders/%s/builds/%d",
			master, builder, buildNum)
		if code, err := r.hc.getJSON(ctx, URL, build); err != nil {
			logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, master.String(), err)
			return nil, err
		}
		return build, nil
	}

	if err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return build, nil
}

func (r *reader) LatestBuilds(ctx context.Context, master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	v := url.Values{}
	v.Add("master", master.Name())
	v.Add("builder", builder)

	URL := fmt.Sprintf("%s/get_builds?%s", chromeBuildExtractURL, v.Encode())
	res := struct {
		Builds []*messages.Build `json:"builds"`
	}{}

	expvars.Add("LatestBuilds", 1)
	defer expvars.Add("LatestBuilds", -1)
	if code, err := r.hc.getJSON(ctx, URL, &res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
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

func contains(arr []string, s string) bool {
	for _, itm := range arr {
		if itm == s {
			return true
		}
	}

	return false
}

func (r *reader) TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	masterValues := r.trCache[master.Name()]
	if len(masterValues) == 0 {
		logging.Debugf(ctx, "no test results for master %s", master.Name())
		return nil, nil
	}

	testValues := masterValues[stepName]
	if len(testValues) == 0 {
		logging.Debugf(ctx, "no test results for master %s test %s", master.Name(), stepName)
		return nil, nil
	}

	if !contains(testValues, builderName) {
		logging.Debugf(ctx, "no test results for master %s test %s builder %s", master.Name(), stepName, builderName)
		return nil, nil
	}

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
	if code, err := r.hc.getJSON(ctx, URL, tr); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return tr, nil
}

func (r *reader) BuildExtract(ctx context.Context, masterURL *messages.MasterLocation) (*messages.BuildExtract, error) {
	URL := fmt.Sprintf("%s/get_master/%s", chromeBuildExtractURL, masterURL.Name())
	ret := &messages.BuildExtract{}

	expvars.Add("BuildExtract", 1)
	defer expvars.Add("BuildExtract", -1)
	code, err := r.hc.getJSON(ctx, URL, ret)

	if code == 404 || code == 403 || code == 401 {
		// FIXME: Don't directly poll so many builders.
		URL = fmt.Sprintf("%s/json", masterURL.String())
		expvars.Add("DirectPoll", 1)
		defer expvars.Add("DirectPoll", -1)
		if code, err := r.hc.getJSON(ctx, URL, ret); err != nil {
			logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, masterURL.String(), err)
			return nil, err
		}
		return ret, nil
	}

	if err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return ret, nil
}

func (r *reader) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", master, builder, buildNum, step)

	expvars.Add("StdioForStep", 1)
	defer expvars.Add("StdioForStep", -1)
	res, _, err := r.hc.getText(ctx, URL)
	return strings.Split(res, "\n"), err
}

func (r *reader) CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error) {
	v := url.Values{}
	v.Add("can", "open")
	v.Add("maxResults", "100")
	v.Add("q", fmt.Sprintf("label:%s", label))

	URL := "https://www.googleapis.com/projecthosting/v2/projects/chromium/issues?" + v.Encode()
	expvars.Add("CrbugIssues", 1)
	defer expvars.Add("CrbugIssues", -1)
	res := &messages.CrbugSearchResults{}
	if code, err := r.hc.getJSON(ctx, URL, res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Items, nil
}

type finditAPIResponse struct {
	Results []*messages.FinditResult `json:"results"`
}

func (r *reader) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	// TODO(martiniss): Remove once perf is supported by findit
	if strings.Contains(master.Name(), "perf") {
		return []*messages.FinditResult{}, nil
	}

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
	if code, err := r.hc.postJSON(ctx, URL, b.Bytes(), res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
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

func (w *writer) PostAlerts(ctx context.Context, alerts *messages.AlertsSummary) error {
	return w.hc.trackRequestStats(func() (length int64, err error) {
		logging.Infof(ctx, "POSTing alerts to %s", w.alertsBase)
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
		defer resp.Body.Close()

		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, w.alertsBase)
			return
		}

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

func (hc *trackingHTTPClient) attemptJSONGet(ctx context.Context, url string, v interface{}) (bool, int, int64, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		logging.Errorf(ctx, "error while creating request: %q, possibly retrying.", err.Error())
		return false, 0, 0, err
	}

	return hc.attemptReq(ctx, req, v)
}

func (hc *trackingHTTPClient) attemptReq(ctx context.Context, r *http.Request, v interface{}) (bool, int, int64, error) {
	r.Header.Set("User-Agent", "Go-http-client/1.1 alerts_dispatcher")
	resp, err := hc.c.Do(r)
	if err != nil {
		logging.Errorf(ctx, "error: %q, possibly retrying.", err.Error())
		return false, 0, 0, err
	}

	defer resp.Body.Close()
	status := resp.StatusCode
	if status != http.StatusOK {
		return false, status, 0, fmt.Errorf("Bad response code: %v", status)
	}

	if err = json.NewDecoder(resp.Body).Decode(v); err != nil {
		logging.Errorf(ctx, "Error decoding response: %v", err)
		return false, status, 0, err
	}
	ct := strings.ToLower(resp.Header.Get("Content-Type"))
	expected := "application/json"
	if !strings.HasPrefix(ct, expected) {
		err = fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\": %s", expected, ct, r.URL)
		return false, status, 0, err
	}
	logging.Infof(ctx, "Fetched(%d) json: %s", status, r.URL)

	return true, status, resp.ContentLength, err
}

// postJSON does a simple HTTP POST on a endpoint, with retries and backoff.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) postJSON(ctx context.Context, url string, data []byte, v interface{}) (status int, err error) {
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	req.Header.Set("User-Agent", "Go-http-client/1.1 alerts_dispatcher")
	req.Header.Set("Content-Type", "application/json")
	if err != nil {
		return 0, err
	}

	err = hc.trackRequestStats(func() (length int64, err error) {
		attempts := 0
		for {
			logging.Infof(ctx, "Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			done, tStatus, length, err := hc.attemptReq(ctx, req, v)
			status = tStatus
			if done {
				return length, err
			}
			if err != nil {
				logging.Errorf(ctx, "Error attempting fetch: %v", err)
			}

			attempts++
			if attempts > maxRetries {
				return 0, fmt.Errorf("error fetching %s, max retries exceeded", url)
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
func (hc *trackingHTTPClient) getJSON(ctx context.Context, url string, v interface{}) (status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {
		attempts := 0
		for {
			logging.Infof(ctx, "Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			done, tStatus, length, err := hc.attemptJSONGet(ctx, url, v)
			status = tStatus
			if done {
				return length, err
			}
			if err != nil {
				logging.Errorf(ctx, "Error attempting fetch: %v", err)
			}

			attempts++
			if attempts > maxRetries {
				return 0, fmt.Errorf("error fetching %s, max retries exceeded", url)
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
func (hc *trackingHTTPClient) getText(ctx context.Context, url string) (ret string, status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {

		logging.Infof(ctx, "Fetching text (%d): %s", hc.currReqs, url)
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

		logging.Infof(ctx, "Fetched(%d) text: %s", resp.StatusCode, url)
		return length, err
	})
	return ret, status, nil
}
