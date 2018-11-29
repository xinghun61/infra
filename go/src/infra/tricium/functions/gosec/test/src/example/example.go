package main

import (
	"fmt"
	"math/rand"
	"os"
)

func main() {
	fmt.Printf(os.Args[1], rand.Int())
}
