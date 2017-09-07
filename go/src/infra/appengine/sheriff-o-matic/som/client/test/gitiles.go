package test

import (
	"encoding/base64"
	"io/ioutil"
	"net/http"
	"strings"
)

// MockGitilesTransport is a test support type to mock out request/response pairs.
type MockGitilesTransport struct {
	Responses map[string]string
}

// RoundTrip implements http.RoundTripper
func (t MockGitilesTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	response := &http.Response{
		Header:     make(http.Header),
		Request:    req,
		StatusCode: http.StatusOK,
	}

	responseBody, ok := t.Responses[req.URL.String()]
	if !ok {
		response.StatusCode = http.StatusNotFound
		return response, nil
	}

	if strings.ToLower(req.FormValue("format")) == "text" {
		responseBody = base64.StdEncoding.EncodeToString([]byte(responseBody))
	}

	response.Body = ioutil.NopCloser(strings.NewReader(responseBody))
	return response, nil
}
