package test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
)

// FakeServer is a test helper to run local in-process http servers for testing fakes.
type FakeServer struct {
	// JSONResponse will always be returned (json-encoded) for any request to the server.
	JSONResponse interface{}
	// PerURLResponse allows test clients to mock out specific URLs that are requested from this server.
	// If a URL matches, the resulting json-encoded blob will be returned, rather than JSONResponse.
	PerURLResponse map[string]interface{}
	// Server is the local in-process server used for faking a service.
	Server *httptest.Server
}

// NewFakeServer returns a new *FakeServer.
// It is up to callers to remember to call FakeServer.Server.Close().
func NewFakeServer() *FakeServer {
	fs := &FakeServer{}
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		data := fs.JSONResponse
		if perURL, ok := fs.PerURLResponse[r.URL.Path]; ok {
			data = perURL
		}

		respData, err := json.Marshal(data)
		if err != nil {
			w.Write([]byte(fmt.Sprintf("FakeServer couldn't marshal json data: %v", err)))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(respData)
	})

	fs.Server = httptest.NewServer(mux)
	return fs
}
