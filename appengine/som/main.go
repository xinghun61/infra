package main

import (
	"html/template"
	"net/http"
)

var (
	mainPage = template.Must(template.ParseFiles("./index.html"))
)

func mainHandler(w http.ResponseWriter, r *http.Request) {
	mainPage.Execute(w, nil)
}

func init() {
	http.HandleFunc("/", mainHandler)
}
