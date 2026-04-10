package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"sync"

	kafka "github.com/segmentio/kafka-go"
)

// SpanMessage matches exactly what our Ingestion API sends to Kafka
type SpanMessage struct {
	AppName      string                 `json:"app_name"`
	TraceID      string                 `json:"trace_id"`
	FunctionName string                 `json:"function_name"`
	FileName     string                 `json:"file_name"`
	LineNumber   int                    `json:"line_number"`
	DurationMs   int                    `json:"duration_ms"`
	Status       string                 `json:"status"`
	SpanOrder    int                    `json:"span_order"`
	Error        map[string]interface{} `json:"error"`
	Metadata     map[string]interface{} `json:"metadata"`
}

func consume(kafkaURL string, db *sql.DB) {
	// Create Kafka reader — this is our consumer
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{kafkaURL},
		Topic:    "raw-logs",
		GroupID:  "flowlog-processors", // consumer group
		MinBytes: 1,
		MaxBytes: 10e6, // 10MB max per message
	})
	defer reader.Close()

	fmt.Println("Waiting for messages from Kafka...")

	// WaitGroup tracks all goroutines
	// We wait for all to finish before shutting down
	var wg sync.WaitGroup

	for {
		// Read next message from Kafka — blocks until message arrives
		msg, err := reader.ReadMessage(context.Background())
		if err != nil {
			log.Println("Error reading message:", err)
			continue
		}

		// Parse JSON message
		var span SpanMessage
		if err := json.Unmarshal(msg.Value, &span); err != nil {
			log.Println("Error parsing message:", err)
			continue
		}

		fmt.Printf("Received span: %s → %s [%s]\n",
			span.TraceID, span.FunctionName, span.Status)

		// Spawn goroutine to process this span
		// Each message processed concurrently — this is the power of Go
		wg.Add(1)
		go func(s SpanMessage) {
			defer wg.Done()
			if err := processSpan(db, s); err != nil {
				log.Printf("Error processing span %s: %v\n", s.TraceID, err)
			}
		}(span)
	}
}