package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"strings"
	"time"

	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

type simpleClient struct {
	Host   string
	Client *http.Client
}

func retry(f func() error, maxAttempts int) error {
	for attempt := 0; attempt < maxAttempts; attempt++ {
		err := f()
		if err == nil {
			return nil
		}

		time.Sleep(time.Duration(math.Pow(2, float64(attempt))) * time.Second)
	}

	return fmt.Errorf("error max retries exceeded")
}

func (sc *simpleClient) attemptReq(ctx context.Context, r *http.Request, v interface{}) (int, error) {
	r.Header.Set("User-Agent", "Go-http-client/1.1 infra/monitoring/client")
	client, err := getAsSelfOAuthClient(ctx)
	if err != nil {
		return 0, err
	}

	resp, err := client.Do(r)
	if err != nil {
		logging.Errorf(ctx, "error: %q, possibly retrying.", err.Error())
		return 0, err
	}
	defer resp.Body.Close()
	status := resp.StatusCode
	if status != http.StatusOK {
		return status, fmt.Errorf("Bad response code: %v", status)
	}

	if err = json.NewDecoder(resp.Body).Decode(v); err != nil {
		logging.Errorf(ctx, "Error decoding response: %v", err)
		return status, err
	}
	ct := strings.ToLower(resp.Header.Get("Content-Type"))
	expected := "application/json"
	if !strings.HasPrefix(ct, expected) {
		err = fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\": %s", expected, ct, r.URL)
		return status, err
	}

	return status, err
}

func (sc *simpleClient) attemptJSONGet(ctx context.Context, url string, v interface{}) (int, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		logging.Errorf(ctx, "error while creating request: %q, possibly retrying.", err.Error())
		return 0, err
	}

	return sc.attemptReq(ctx, req, v)
}

// getJSON does a simple HTTP GET on a getJSON endpoint.
//
// Returns the status code and the error, if any.
func (sc *simpleClient) getJSON(ctx context.Context, url string, v interface{}) (status int, err error) {
	err = retry(func() error {
		status, err := sc.attemptJSONGet(ctx, url, v)
		if err != nil {
			logging.Errorf(ctx, "Error attempting fetch: %v", err)
			return err
		}

		if status >= 400 && status < 500 {
			return fmt.Errorf("HTTP status %d, not retrying: %s", status, url)
		}

		return nil
	}, maxRetries)
	return status, err
}

// postJSON does a simple HTTP POST on a endpoint, with retries and backoff.
//
// Returns the status code and the error, if any.
func (sc *simpleClient) postJSON(ctx context.Context, url string, data []byte, v interface{}) (status int, err error) {
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	req.Header.Set("User-Agent", "Go-http-client/1.1 alerts_dispatcher")
	req.Header.Set("Content-Type", "application/json")
	if err != nil {
		return 0, err
	}
	err = retry(func() error {
		status, err = sc.attemptReq(ctx, req, v)
		if err != nil {
			logging.Errorf(ctx, "Error attempting POST: %v", err)
			return err
		}
		if status >= 400 && status < 500 {
			return fmt.Errorf("HTTP status %d, not retrying: %s", status, url)
		}

		return nil
	}, maxRetries)

	return status, err
}
