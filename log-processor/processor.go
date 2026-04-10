package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"

	_ "github.com/lib/pq" // PostgreSQL driver
)

// initDB connects to PostgreSQL
func initDB(dbURL string) (*sql.DB, error) {
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, err
	}

	// Test the connection
	if err := db.Ping(); err != nil {
		return nil, err
	}

	return db, nil
}

// processSpan writes a span to PostgreSQL
// This runs in its own goroutine
func processSpan(db *sql.DB, span SpanMessage) error {
	// Step 1 — Get or create the app
	appID, err := getOrCreateApp(db, span.AppName)
	if err != nil {
		return fmt.Errorf("failed to get app: %w", err)
	}

	// Step 2 — Get or create the trace
	err = getOrCreateTrace(db, span.TraceID, appID)
	if err != nil {
		return fmt.Errorf("failed to get trace: %w", err)
	}

	// Step 3 — Insert the span
	spanID, err := insertSpan(db, span)
	if err != nil {
		return fmt.Errorf("failed to insert span: %w", err)
	}

	// Step 4 — Insert error if span failed
	if span.Status == "FAILED" && span.Error != nil {
		err = insertError(db, spanID, span.Error)
		if err != nil {
			log.Printf("Failed to insert error for span %s: %v\n", spanID, err)
		}
	}

	// Step 5 — Update trace status if failed
	if span.Status == "FAILED" {
		updateTraceStatus(db, span.TraceID, "FAILED")
	}

	fmt.Printf("✓ Saved span: %s → %s\n", span.FunctionName, span.Status)
	return nil
}

func getOrCreateApp(db *sql.DB, appName string) (string, error) {
	var appID string

	// Try to find existing app
	err := db.QueryRow(
		"SELECT id FROM apps WHERE name = $1", appName,
	).Scan(&appID)

	if err == sql.ErrNoRows {
		// App doesn't exist — create it
		err = db.QueryRow(
			`INSERT INTO apps (name, api_key) 
			 VALUES ($1, gen_random_uuid()::text) 
			 ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
			 RETURNING id`,
			appName,
		).Scan(&appID)
	}

	return appID, err
}

func getOrCreateTrace(db *sql.DB, traceID string, appID string) error {
	_, err := db.Exec(
		`INSERT INTO traces (trace_id, app_id, status)
		 VALUES ($1, $2, 'SUCCESS')
		 ON CONFLICT (trace_id) DO NOTHING`,
		traceID, appID,
	)
	return err
}

func insertSpan(db *sql.DB, span SpanMessage) (string, error) {
	var spanID string

	// Convert metadata to JSON string
	metadataJSON, _ := json.Marshal(span.Metadata)

	err := db.QueryRow(
		`INSERT INTO spans 
		 (trace_id, function_name, file_name, line_number, duration_ms, status, span_order, metadata)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		 RETURNING id`,
		span.TraceID,
		span.FunctionName,
		span.FileName,
		span.LineNumber,
		span.DurationMs,
		span.Status,
		span.SpanOrder,
		string(metadataJSON),
	).Scan(&spanID)

	return spanID, err
}

func insertError(db *sql.DB, spanID string, errorData map[string]interface{}) error {
	_, err := db.Exec(
		`INSERT INTO errors (span_id, error_type, error_message, stack_trace)
		 VALUES ($1, $2, $3, $4)`,
		spanID,
		errorData["error_type"],
		errorData["error_message"],
		errorData["stack_trace"],
	)
	return err
}

func updateTraceStatus(db *sql.DB, traceID string, status string) {
	db.Exec(
		"UPDATE traces SET status = $1 WHERE trace_id = $2",
		status, traceID,
	)
}