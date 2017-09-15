// Package main implements the Hello analyzer.
package main

import (
	"flag"
	"fmt"
	"log"

	"infra/tricium/api/v1"
)

func main() {
	prefix := flag.String("prefix", "", "Output path prefix")
	flag.Parse()

	msg := &tricium.Data_Results{
		Platforms: 0,
		Comments: []*tricium.Data_Comment{
			{
				Category: "Hello",
				Message:  "Hello",
			},
		},
	}
	path, err := tricium.WriteDataType(*prefix, msg)
	if err != nil {
		log.Fatalf("failed to run hello analyzer: %v", err)
	}
	fmt.Printf("Wrote Hello comment, path: %q, prefix: %q\n", path, *prefix)
}
