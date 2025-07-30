```go
package main

import (
	"fmt"
	"sync"
)

func main() {
	words := []string{"backend", "is", "my", "passion"}
	var wg sync.WaitGroup

	for _, w := range words {
		wg.Add(1)
		go func(word string) {
			defer wg.Done()
			fmt.Print(word, " ")
		}(w)
	}

	wg.Wait()
}
```
