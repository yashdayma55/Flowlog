package main

import (
	"fmt"
	"log"
	"os"
)

func main() {
	fmt.Println("FlowLog Log Processor starting...")

	// Get config from environment variables
	kafkaURL := getEnv("KAFKA_URL", "localhost:9092")
	dbURL := getEnv("DB_URL", "postgres://flowlog:flowlog123@localhost:5433/flowlog?sslmode=disable")

	fmt.Printf("Connecting to Kafka: %s\n", kafkaURL)
	fmt.Printf("Connecting to DB: %s\n", dbURL)

	// Initialize database connection
	db, err := initDB(dbURL)
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	defer db.Close()
	fmt.Println("Connected to PostgreSQL ✓")

	// Start consuming from Kafka
	fmt.Println("Starting Kafka consumer...")
	consume(kafkaURL, db)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}