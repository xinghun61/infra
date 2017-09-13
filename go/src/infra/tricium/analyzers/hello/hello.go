// Package main implements the Hello analyzer.
package main

import (
	"fmt"

	"infra/tricium/api/v1"
)

func main() {
	msg := &tricium.Data_Results{
		Platforms: 0,
		Comments: []*tricium.Data_Comment{
			{
				Category: "Hello",
				Message:  "Hello",
			},
		},
	}
	if err := tricium.WriteDataType(msg); err != nil {
		panic(fmt.Sprintf("failed to run hello analyzer: %v", err))
	}
}
