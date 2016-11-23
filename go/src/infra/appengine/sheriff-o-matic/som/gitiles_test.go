package som

import (
	"encoding/base64"
	"io/ioutil"
	"net/http"
	"strings"
)

type mockGitilesTransport struct {
	responses map[string]string
}

func (t mockGitilesTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	response := &http.Response{
		Header:     make(http.Header),
		Request:    req,
		StatusCode: http.StatusOK,
	}

	responseBody, ok := t.responses[req.URL.String()]
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
