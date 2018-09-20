package main

// This command generates a compiled-in version of loader.html so
// that the wct binary can serve it without external file dependencies.

import (
	"io"
	"os"
)

func main() {
	in, _ := os.Open("./loader.html")
	defer in.Close()
	out, _ := os.Create("loader.go")
	defer out.Close()
	out.Write([]byte("package main\n\nconst (\n"))
	out.Write([]byte("\tloaderHTMLTemplate = `"))
	io.Copy(out, in)
	out.Write([]byte("`\n"))
	out.Write([]byte(")\n"))
}
