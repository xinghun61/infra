// Package buildextract implements a HTTP client for the Chrome
// build extracts API.
//
// Example:
//
//   c := buildextract.NewClient(http.DefaultClient)
//   data, err := c.GetMasterJSON("chromium.mac")
//   // Error check elided.
//   io.Copy(os.Stdout, data)
//   data.Close()
//
package buildextract

import (
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/url"
	"path"
	"strconv"
)

// BaseURL is the base URL of the Chrome build extract API.
const BaseURL = "https://chrome-build-extract.appspot.com"

// StatusError is returned when the HTTP roundtrip succeeds,
// but the response's status code is not http.StatusOK.
type StatusError struct {
	StatusCode int
	Status     string
	Body       []byte
}

func (e *StatusError) Error() string {
	return fmt.Sprintf("buildextract: response error: %s", e.Status)
}

// Client is the HTTP client and configuration used to make requests.
// Safe for concurrent use.
type Client struct {
	HTTPClient *http.Client
	BaseURL    string
}

// NewClient returns a Client initialized with the supplied
// http.Client. The returned client is ready to make requests to the API.
func NewClient(c *http.Client) *Client {
	return &Client{
		HTTPClient: c,
		BaseURL:    BaseURL,
	}
}

func (c *Client) doRequest(req *http.Request) (io.ReadCloser, error) {
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		b, _ := ioutil.ReadAll(resp.Body) // Ignore error.
		return nil, &StatusError{
			StatusCode: resp.StatusCode,
			Status:     resp.Status,
			Body:       b,
		}
	}

	return resp.Body, nil
}

// GetMasterJSON returns the masters data as JSON for the supplied arguments.
//
// If the returned error is non-nil, the caller is responsible for
// closing the retured io.ReadCloser.
func (c *Client) GetMasterJSON(master string) (io.ReadCloser, error) {
	u, err := url.Parse(c.BaseURL)
	if err != nil {
		return nil, err
	}
	u.Path = path.Join(u.Path, "/get_master", master)

	return c.doRequest(&http.Request{
		Method: "GET",
		URL:    u,
	})
}

// GetBuildsJSON returns the builds data as JSON for the supplied
// arguments.
//
// If the returned error is non-nil, the caller is responsible for
// closing the retured io.ReadCloser.
func (c *Client) GetBuildsJSON(builder, master string, numBuilds int) (io.ReadCloser, error) {
	u, err := url.Parse(c.BaseURL)
	if err != nil {
		return nil, err
	}
	u.Path = path.Join(u.Path, "/get_builds")

	val := url.Values{}
	val.Set("builder", builder)
	val.Set("master", master)
	val.Set("num_builds", strconv.Itoa(numBuilds))
	u.RawQuery = val.Encode()

	return c.doRequest(&http.Request{
		Method: "GET",
		URL:    u,
	})
}
