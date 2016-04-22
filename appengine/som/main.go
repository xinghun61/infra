package main

import (
	"html/template"
	"io/ioutil"
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/memcache"
)

var (
	mainPage = template.Must(template.ParseFiles("./index.html"))
)

func mainHandler(w http.ResponseWriter, r *http.Request) {
	mainPage.Execute(w, nil)
}

func fakeAPIHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	switch r.Method {
	case "GET":
		item, err := memcache.Get(ctx, r.URL.Path)
		if err == memcache.ErrCacheMiss {
			http.Error(w, err.Error(), 404)
			return
		} else if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}

		w.Write(item.Value)
	case "POST":
		data, err := ioutil.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}

		item := &memcache.Item{
			Key:   r.URL.Path,
			Value: data,
		}
		if err := memcache.Set(ctx, item); err != nil {
			http.Error(w, err.Error(), 500)
		}
	}
}

func init() {
	http.HandleFunc("/api/", fakeAPIHandler)
	http.HandleFunc("/", mainHandler)
}
