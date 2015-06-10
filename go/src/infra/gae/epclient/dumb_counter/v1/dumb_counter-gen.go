// Package dumb_counter provides access to the .
//
// Usage example:
//
//   import "google.golang.org/api/dumb_counter/v1"
//   ...
//   dumb_counterService, err := dumb_counter.New(oauthHttpClient)
package dumb_counter

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"golang.org/x/net/context"
	"google.golang.org/api/googleapi"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

// Always reference these packages, just in case the auto-generated code
// below doesn't.
var _ = bytes.NewBuffer
var _ = strconv.Itoa
var _ = fmt.Sprintf
var _ = json.NewDecoder
var _ = io.Copy
var _ = url.Parse
var _ = googleapi.Version
var _ = errors.New
var _ = strings.Replace
var _ = context.Background

const apiId = "dumb_counter:v1"
const apiName = "dumb_counter"
const apiVersion = "v1"
const basePath = "http://localhost:8080/_ah/api/dumb_counter/v1/"

func New(client *http.Client) (*Service, error) {
	if client == nil {
		return nil, errors.New("client is nil")
	}
	s := &Service{client: client, BasePath: basePath}
	return s, nil
}

type Service struct {
	client    *http.Client
	BasePath  string // API endpoint base URL
	UserAgent string // optional additional User-Agent fragment
}

func (s *Service) userAgent() string {
	if s.UserAgent == "" {
		return googleapi.UserAgent
	}
	return googleapi.UserAgent + " " + s.UserAgent
}

type AddReq struct {
	Delta int64 `json:"Delta,omitempty,string"`

	Name string `json:"Name,omitempty"`
}

type AddRsp struct {
	Cur int64 `json:"Cur,omitempty,string"`

	Prev int64 `json:"Prev,omitempty,string"`
}

type CASReq struct {
	Name string `json:"Name,omitempty"`

	NewVal int64 `json:"NewVal,omitempty,string"`

	OldVal int64 `json:"OldVal,omitempty,string"`
}

type Counter struct {
	ID string `json:"ID,omitempty"`

	Val int64 `json:"Val,omitempty,string"`
}

type CurrentValueRsp struct {
	Val int64 `json:"Val,omitempty,string"`
}

type ListRsp struct {
	Counters []*Counter `json:"Counters,omitempty"`
}

// method id "dumb_counter.add":

type AddCall struct {
	s      *Service
	Name   string
	addreq *AddReq
	opt_   map[string]interface{}
}

// Add: Add an an amount to a particular counter
func (s *Service) Add(Name string, addreq *AddReq) *AddCall {
	c := &AddCall{s: s, opt_: make(map[string]interface{})}
	c.Name = Name
	c.addreq = addreq
	return c
}

// Fields allows partial responses to be retrieved.
// See https://developers.google.com/gdata/docs/2.0/basics#PartialResponse
// for more information.
func (c *AddCall) Fields(s ...googleapi.Field) *AddCall {
	c.opt_["fields"] = googleapi.CombineFields(s)
	return c
}

func (c *AddCall) Do() (*AddRsp, error) {
	var body io.Reader = nil
	body, err := googleapi.WithoutDataWrapper.JSONReader(c.addreq)
	if err != nil {
		return nil, err
	}
	ctype := "application/json"
	params := make(url.Values)
	params.Set("alt", "json")
	if v, ok := c.opt_["fields"]; ok {
		params.Set("fields", fmt.Sprintf("%v", v))
	}
	urls := googleapi.ResolveRelative(c.s.BasePath, "counter/{Name}")
	urls += "?" + params.Encode()
	req, _ := http.NewRequest("POST", urls, body)
	googleapi.Expand(req.URL, map[string]string{
		"Name": c.Name,
	})
	req.Header.Set("Content-Type", ctype)
	req.Header.Set("User-Agent", c.s.userAgent())
	res, err := c.s.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer googleapi.CloseBody(res)
	if err := googleapi.CheckResponse(res); err != nil {
		return nil, err
	}
	var ret *AddRsp
	if err := json.NewDecoder(res.Body).Decode(&ret); err != nil {
		return nil, err
	}
	return ret, nil
	// {
	//   "description": "Add an an amount to a particular counter",
	//   "httpMethod": "POST",
	//   "id": "dumb_counter.add",
	//   "parameterOrder": [
	//     "Name"
	//   ],
	//   "parameters": {
	//     "Name": {
	//       "location": "path",
	//       "required": true,
	//       "type": "string"
	//     }
	//   },
	//   "path": "counter/{Name}",
	//   "request": {
	//     "$ref": "AddReq",
	//     "parameterName": "resource"
	//   },
	//   "response": {
	//     "$ref": "AddRsp"
	//   }
	// }

}

// method id "dumb_counter.cas":

type CasCall struct {
	s      *Service
	Name   string
	casreq *CASReq
	opt_   map[string]interface{}
}

// Cas: Compare and swap a counter value
func (s *Service) Cas(Name string, casreq *CASReq) *CasCall {
	c := &CasCall{s: s, opt_: make(map[string]interface{})}
	c.Name = Name
	c.casreq = casreq
	return c
}

// Fields allows partial responses to be retrieved.
// See https://developers.google.com/gdata/docs/2.0/basics#PartialResponse
// for more information.
func (c *CasCall) Fields(s ...googleapi.Field) *CasCall {
	c.opt_["fields"] = googleapi.CombineFields(s)
	return c
}

func (c *CasCall) Do() error {
	var body io.Reader = nil
	body, err := googleapi.WithoutDataWrapper.JSONReader(c.casreq)
	if err != nil {
		return err
	}
	ctype := "application/json"
	params := make(url.Values)
	params.Set("alt", "json")
	if v, ok := c.opt_["fields"]; ok {
		params.Set("fields", fmt.Sprintf("%v", v))
	}
	urls := googleapi.ResolveRelative(c.s.BasePath, "counter/{Name}/cas")
	urls += "?" + params.Encode()
	req, _ := http.NewRequest("POST", urls, body)
	googleapi.Expand(req.URL, map[string]string{
		"Name": c.Name,
	})
	req.Header.Set("Content-Type", ctype)
	req.Header.Set("User-Agent", c.s.userAgent())
	res, err := c.s.client.Do(req)
	if err != nil {
		return err
	}
	defer googleapi.CloseBody(res)
	if err := googleapi.CheckResponse(res); err != nil {
		return err
	}
	return nil
	// {
	//   "description": "Compare and swap a counter value",
	//   "httpMethod": "POST",
	//   "id": "dumb_counter.cas",
	//   "parameterOrder": [
	//     "Name"
	//   ],
	//   "parameters": {
	//     "Name": {
	//       "location": "path",
	//       "required": true,
	//       "type": "string"
	//     }
	//   },
	//   "path": "counter/{Name}/cas",
	//   "request": {
	//     "$ref": "CASReq",
	//     "parameterName": "resource"
	//   }
	// }

}

// method id "dumb_counter.currentvalue":

type CurrentvalueCall struct {
	s    *Service
	Name string
	opt_ map[string]interface{}
}

// Currentvalue: Returns the current value held by the named counter
func (s *Service) Currentvalue(Name string) *CurrentvalueCall {
	c := &CurrentvalueCall{s: s, opt_: make(map[string]interface{})}
	c.Name = Name
	return c
}

// Fields allows partial responses to be retrieved.
// See https://developers.google.com/gdata/docs/2.0/basics#PartialResponse
// for more information.
func (c *CurrentvalueCall) Fields(s ...googleapi.Field) *CurrentvalueCall {
	c.opt_["fields"] = googleapi.CombineFields(s)
	return c
}

func (c *CurrentvalueCall) Do() (*CurrentValueRsp, error) {
	var body io.Reader = nil
	params := make(url.Values)
	params.Set("alt", "json")
	if v, ok := c.opt_["fields"]; ok {
		params.Set("fields", fmt.Sprintf("%v", v))
	}
	urls := googleapi.ResolveRelative(c.s.BasePath, "counter/{Name}")
	urls += "?" + params.Encode()
	req, _ := http.NewRequest("GET", urls, body)
	googleapi.Expand(req.URL, map[string]string{
		"Name": c.Name,
	})
	req.Header.Set("User-Agent", c.s.userAgent())
	res, err := c.s.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer googleapi.CloseBody(res)
	if err := googleapi.CheckResponse(res); err != nil {
		return nil, err
	}
	var ret *CurrentValueRsp
	if err := json.NewDecoder(res.Body).Decode(&ret); err != nil {
		return nil, err
	}
	return ret, nil
	// {
	//   "description": "Returns the current value held by the named counter",
	//   "httpMethod": "GET",
	//   "id": "dumb_counter.currentvalue",
	//   "parameterOrder": [
	//     "Name"
	//   ],
	//   "parameters": {
	//     "Name": {
	//       "location": "path",
	//       "required": true,
	//       "type": "string"
	//     }
	//   },
	//   "path": "counter/{Name}",
	//   "response": {
	//     "$ref": "CurrentValueRsp"
	//   }
	// }

}

// method id "dumb_counter.list":

type ListCall struct {
	s    *Service
	opt_ map[string]interface{}
}

// List: Returns all of the available counters
func (s *Service) List() *ListCall {
	c := &ListCall{s: s, opt_: make(map[string]interface{})}
	return c
}

// Fields allows partial responses to be retrieved.
// See https://developers.google.com/gdata/docs/2.0/basics#PartialResponse
// for more information.
func (c *ListCall) Fields(s ...googleapi.Field) *ListCall {
	c.opt_["fields"] = googleapi.CombineFields(s)
	return c
}

func (c *ListCall) Do() (*ListRsp, error) {
	var body io.Reader = nil
	params := make(url.Values)
	params.Set("alt", "json")
	if v, ok := c.opt_["fields"]; ok {
		params.Set("fields", fmt.Sprintf("%v", v))
	}
	urls := googleapi.ResolveRelative(c.s.BasePath, "counter")
	urls += "?" + params.Encode()
	req, _ := http.NewRequest("GET", urls, body)
	googleapi.SetOpaque(req.URL)
	req.Header.Set("User-Agent", c.s.userAgent())
	res, err := c.s.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer googleapi.CloseBody(res)
	if err := googleapi.CheckResponse(res); err != nil {
		return nil, err
	}
	var ret *ListRsp
	if err := json.NewDecoder(res.Body).Decode(&ret); err != nil {
		return nil, err
	}
	return ret, nil
	// {
	//   "description": "Returns all of the available counters",
	//   "httpMethod": "GET",
	//   "id": "dumb_counter.list",
	//   "path": "counter",
	//   "response": {
	//     "$ref": "ListRsp"
	//   }
	// }

}
