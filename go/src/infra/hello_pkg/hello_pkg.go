package hello_pkg

import "fmt"
import "code.google.com/p/goauth2/oauth"

// Demonstrate that third party package is usable.
var config = &oauth.Config{
	ClientId:     "123",
	ClientSecret: "456",
	Scope:        "https://www.googleapis.com/auth/buzz",
	AuthURL:      "https://accounts.google.com/o/oauth2/auth",
	TokenURL:     "https://accounts.google.com/o/oauth2/token",
	RedirectURL:  "http://you.example.org/handler",
}

func Greetings(text string) {
	fmt.Printf("%s, %v!\n", text, config)
}
