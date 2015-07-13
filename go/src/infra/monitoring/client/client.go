// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"

	"github.com/luci/luci-go/common/logging/gologger"

	"infra/monitoring/messages"
)

var (
	log = gologger.Get()
)

// MasterURL returns the builder URL for the given master.
func MasterURL(master string) string {
	return fmt.Sprintf("https://build.chromium.org/p/%s", master)
}

// BuilderURL returns the builder URL for the given master and builder.
func BuilderURL(master, builder string) string {
	return fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s", master, oldEscape(builder))
}

// BuildURL returns the build URL for the given master, builder and build number.
func BuildURL(master, builder string, buildNum int64) string {
	return fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d", master, oldEscape(builder), buildNum)
}

// StepURL returns the step URL for the given master, builder, step and build number.
func StepURL(master, builder, step string, buildNum int64) string {
	return fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s",
		master, oldEscape(builder), buildNum, oldEscape(step))
}

// Sigh.  build.chromium.org doesn't accept + as an escaped space in URL paths.
func oldEscape(s string) string {
	return strings.Replace(url.QueryEscape(s), "+", "%20", -1)
}

// Client provides access to read status information from various parts of chrome
// developer infrastructure.
type Reader interface {
	// Build fetches the build summary for master, builder and buildNum
	// from build.chromium.org.
	Build(master, builder string, buildNum int64) (*messages.Build, error)

	// LatestBuilds fetches a list of recent build summaries for master and builder
	// from build.chromium.org.
	LatestBuilds(master, build string) ([]*messages.Build, error)

	// TestResults fetches the results of a step failure's test run.
	TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error)

	// BuildExtract fetches build information for master from CBE.
	BuildExtract(master string) (*messages.BuildExtract, error)

	// StdioForStep fetches the standard output for a given build step, and an error if any
	// occurred.
	StdioForStep(master, builder, step string, buildNum int64) ([]string, error)

	// DumpStats logs stats about the client to stdout.
	DumpStats()
}

type Writer interface {
	// PostAlerts posts alerts to Sheriff-o-Matic.
	PostAlerts(alerts *messages.Alerts) error
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
}

type writer struct {
	hc         *trackingHTTPClient
	alertsBase string
}

// NewReader returns a new Reader, which will read data from various chrome infra
// data sources.
func NewReader() Reader {
	return &reader{hc: &trackingHTTPClient{c: http.DefaultClient}}
}

func (r *reader) Build(master, builder string, buildNum int64) (*messages.Build, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/json/builders/%s/builds/%d",
		master, builder, buildNum)

	bld := &messages.Build{}
	if code, err := r.hc.getJSON(URL, bld); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return bld, nil
}

func (r *reader) LatestBuilds(master, builder string) ([]*messages.Build, error) {
	v := url.Values{}
	v.Add("master", master)
	v.Add("builder", builder)

	URL := fmt.Sprintf("https://chrome-build-extract.appspot.com/get_builds?%s", v.Encode())
	res := struct {
		Builds []*messages.Build `json:"builds"`
	}{}

	if code, err := r.hc.getJSON(URL, &res); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Builds, nil
}

func (r *reader) TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	// This substitution is done in the existing builder_alerts python code.
	if stepName == "webkit_tests" {
		stepName = "layout-tests"
	}

	v := url.Values{}
	v.Add("name", "full_results.json")
	v.Add("master", masterName)
	v.Add("builder", builderName)
	v.Add("buildnumber", fmt.Sprintf("%d", buildNumber))
	v.Add("testtype", stepName)

	URL := fmt.Sprintf("https://test-results.appspot.com/testfile?%s", v.Encode())
	tr := &messages.TestResults{}

	if code, err := r.hc.getJSON(URL, tr); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return tr, nil
}

func (r *reader) BuildExtract(master string) (*messages.BuildExtract, error) {
	URL := fmt.Sprintf("https://chrome-build-extract.appspot.com/get_master/%s", master)
	ret := &messages.BuildExtract{}
	if code, err := r.hc.getJSON(URL, ret); err != nil {
		log.Errorf("Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}
	return ret, nil
}

func (r *reader) StdioForStep(master, builder, step string, buildNum int64) ([]string, error) {
	URL := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", master, builder, buildNum, step)
	res, _, err := r.hc.getText(URL)
	return strings.Split(res, "\n"), err
}

func (r *reader) DumpStats() {
	r.hc.dumpStats()
}

// NewWriter returns a new Client, which will post alerts to alertsBase.
func NewWriter(alertsBase string) Writer {
	return &writer{hc: &trackingHTTPClient{c: http.DefaultClient}, alertsBase: alertsBase}
}

func (w *writer) PostAlerts(alerts *messages.Alerts) error {
	return w.hc.trackRequestStats(func() (length int64, err error) {
		log.Infof("POSTing alerts to %s", w.alertsBase)
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

func (hc *trackingHTTPClient) startReq() {
	atomic.AddInt64(&hc.currReqs, 1)
	atomic.AddInt64(&hc.totalReqs, 1)
}

func (hc *trackingHTTPClient) endReq(r int64) {
	atomic.AddInt64(&hc.currReqs, -1)
	atomic.AddInt64(&hc.totalBytes, r)
}

func (hc *trackingHTTPClient) errReq() {
	atomic.AddInt64(&hc.currReqs, -1)
	atomic.AddInt64(&hc.totalErrs, 1)
}

func (hc *trackingHTTPClient) trackRequestStats(cb func() (int64, error)) error {
	var err error
	length := int64(0)
	hc.startReq()
	defer func() {
		if err != nil {
			hc.errReq()
		} else {
			hc.endReq(length)
		}
	}()
	length, err = cb()
	return err
}

// getJSON does a simple HTTP GET on a getJSON endpoint.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) getJSON(url string, v interface{}) (status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {
		log.Infof("Fetching json (%d): %s", hc.currReqs, url)
		resp, err := hc.c.Get(url)
		status = resp.StatusCode
		if err != nil {
			return
		}
		defer resp.Body.Close()
		if err = json.NewDecoder(resp.Body).Decode(v); err != nil {
			return
		}
		ct := strings.ToLower(resp.Header.Get("Content-Type"))
		expected := "application/json"
		if ct != expected {
			err = fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\": %s", expected, ct, url)
			return
		}
		if resp.StatusCode >= 400 {
			err = fmt.Errorf("http status %d: %s", resp.StatusCode, url)
			return
		}

		length = resp.ContentLength

		log.Infof("Fetched(%d) json: %s", resp.StatusCode, url)
		return length, err
	})

	return status, err
}

// getText does a simple HTTP GET on a text endpoint.
//
// Returns the status code and the error, if any.
func (hc *trackingHTTPClient) getText(url string) (ret string, status int, err error) {
	err = hc.trackRequestStats(func() (length int64, err error) {

		log.Infof("Fetching text (%d): %s", hc.currReqs, url)
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

		log.Infof("Fetched(%d) text: %s", resp.StatusCode, url)
		return length, err
	})
	return ret, status, nil
}

func (hc *trackingHTTPClient) dumpStats() {
	log.Infof("%d reqs total, %d errors, %d current", hc.totalReqs, hc.totalErrs, hc.currReqs)
	log.Infof("%d bytes read", hc.totalBytes)
}
