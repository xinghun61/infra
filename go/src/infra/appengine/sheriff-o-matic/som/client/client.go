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

	"infra/monitoring/messages"
	"infra/monorail"

	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/milo/api/proto"
	"go.chromium.org/luci/server/auth"
)

type contextKey string

const (
	maxRetries = 3
	// FYI https://github.com/golang/go/issues/9405 in Go 1.4
	// http timeout errors are logged as "use of closed network connection"
	timeout = 5 * time.Second

	clientReaderKey = contextKey("infra-client-reader")

	crRevKey         = contextKey("infra-client-crrev")
	buildBotKey      = contextKey("infra-client-buildbot")
	finditKey        = contextKey("infra-client-findit")
	gerritKey        = contextKey("infra-client-gerrit")
	logdogKey        = contextKey("infra-client-logdog")
	miloBuildbotKey  = contextKey("infra-client-milo-buildbot")
	miloBuildInfoKey = contextKey("infra-client-milo-buildinfo")
	monorailKey      = contextKey("infra-client-monorail")
	swarmingKey      = contextKey("infra-client-swarming")
	testResultsKey   = contextKey("infra-client-testrestults")
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
}

type writer struct {
	hc         *trackingHTTPClient
	alertsBase string
}

// BuilderData is the data returned from the GET "/data/builders" endpoint.
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

func newReader(ctx context.Context, httpClient *http.Client) (*reader, error) {
	if httpClient == nil {
		httpClient = http.DefaultClient
	}

	r := &reader{
		hc: &trackingHTTPClient{
			c: httpClient,
		},
		bCache: map[string]*messages.Build{},
	}

	return r, nil
}

// NewReader returns a new default reader implementation, which will read data from various chrome infra
// data sources.
func NewReader(ctx context.Context) (readerType, error) {
	return newReader(ctx, http.DefaultClient)
}

func cacheKeyForBuild(master *messages.MasterLocation, builder string, number int64) string {
	return filepath.FromSlash(
		fmt.Sprintf("%s/%s/%d.json", url.QueryEscape(master.String()), url.QueryEscape(builder), number))
}

func (r *reader) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", master, builder, buildNum, step)

	expvars.Add("StdioForStep", 1)
	defer expvars.Add("StdioForStep", -1)
	res, _, err := r.hc.getText(ctx, URL)
	return strings.Split(res, "\n"), err
}

func contains(arr []string, s string) bool {
	for _, itm := range arr {
		if itm == s {
			return true
		}
	}

	return false
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

// FinditAPIResponse represents a response from the findit api.
type FinditAPIResponse struct {
	Results []*messages.FinditResult `json:"results"`
}

func (r *reader) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	findit := GetFindit(ctx)

	ret, err := findit.Findit(ctx, master, builder, buildNum, failedSteps)
	if err != nil {
		return nil, err
	}

	return ret, nil
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

	return true, status, resp.ContentLength, err
}

// postJSON does a simple HTTP POST on a endpoint, with retries and backoff.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) postJSON(ctx context.Context, url string, data []byte, v interface{}) (status int, err error) {
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	if err != nil {
		return 0, err
	}

	err = hc.trackRequestStats(func() (length int64, err error) {
		attempts := 0
		for {
			if attempts > 0 {
				logging.Infof(ctx, "Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			}
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
			if attempts > 0 {
				logging.Infof(ctx, "Fetching json (%d in flight, attempt %d of %d): %s", hc.currReqs, attempts, maxRetries, url)
			}
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

		if resp.StatusCode != 200 {
			logging.Infof(ctx, "Fetched(%d) text: %s", resp.StatusCode, url)
		}
		return length, err
	})
	return ret, status, nil
}

// getAsSelfOAuthClient returns a client capable of making HTTP requests authenticated
// with OAuth access token for userinfo.email scope.
func getAsSelfOAuthClient(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

// WithMonorail registers a new Monorail client instance pointed at baseURL.
func WithMonorail(c context.Context, baseURL string) context.Context {
	client, err := getAsSelfOAuthClient(c)

	if err != nil {
		panic("No OAuth client in context")
	}

	mr := monorail.NewEndpointsClient(client, baseURL+"/_ah/api/monorail/v1/")

	c = context.WithValue(c, monorailKey, mr)
	return c
}

// GetMonorail returns the currently registered monorail client, or panics.
func GetMonorail(c context.Context) monorail.MonorailClient {
	v := c.Value(monorailKey)
	ret, ok := v.(monorail.MonorailClient)
	if !ok {
		panic("No Monorail client set in context")
	}
	return ret
}

// WithProdClients returns a context for connecting to production services.
func WithProdClients(ctx context.Context) context.Context {
	ctx = WithCrRev(ctx, "https://cr-rev.appspot.com")
	ctx = WithFindit(ctx, "https://findit-for-me.appspot.com")

	client, err := getAsSelfOAuthClient(ctx)
	if err != nil {
		panic("No OAuth client in context")
	}

	miloPRPCClient := &prpc.Client{
		C:       client,
		Host:    "luci-milo.appspot.com",
		Options: prpc.DefaultOptions(),
	}
	miloBuildbot := milo.NewBuildbotPRPCClient(miloPRPCClient)
	miloBuildInfo := milo.NewBuildInfoPRPCClient(miloPRPCClient)
	ctx = WithMiloBuildbot(ctx, miloBuildbot)
	ctx = WithMiloBuildInfo(ctx, miloBuildInfo)

	ctx = WithMonorail(ctx, "https://monorail-prod.appspot.com")
	ctx = WithTestResults(ctx, "https://test-results.appspot.com")

	reader, err := newReader(ctx, &http.Client{Transport: urlfetch.Get(ctx)})
	if err != nil {
		panic(fmt.Sprintf("creating newReader: %v", err))
	}
	memcachingReader := NewMemcacheReader(reader)
	ctx = WithReader(ctx, memcachingReader)

	return ctx
}

// WithStagingClients returns a context for connecting to staging services.
func WithStagingClients(ctx context.Context) context.Context {
	ctx = WithCrRev(ctx, "https://cr-rev.appspot.com")
	ctx = WithFindit(ctx, "https://findit-for-me-staging.appspot.com")

	client, err := getAsSelfOAuthClient(ctx)
	if err != nil {
		panic("No OAuth client in context")
	}

	miloPRPCClient := &prpc.Client{
		C:       client,
		Host:    "luci-milo.appspot.com",
		Options: prpc.DefaultOptions(),
	}
	miloBuildbot := milo.NewBuildbotPRPCClient(miloPRPCClient)
	miloBuildInfo := milo.NewBuildInfoPRPCClient(miloPRPCClient)
	ctx = WithMiloBuildbot(ctx, miloBuildbot)
	ctx = WithMiloBuildInfo(ctx, miloBuildInfo)

	ctx = WithMonorail(ctx, "https://monorail-staging.appspot.com")
	ctx = WithTestResults(ctx, "https://test-results.appspot.com")

	reader, err := newReader(ctx, &http.Client{Transport: urlfetch.Get(ctx)})
	if err != nil {
		panic(fmt.Sprintf("creating newReader: %v", err))
	}
	memcachingReader := NewMemcacheReader(reader)
	ctx = WithReader(ctx, memcachingReader)

	return ctx
}
