package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"
)

type Command struct {
	Command     string `json:"command"`
	ServerID    int    `json:"server_id"`
	MemberID    int    `json:"member_id"`
	PositionX   int    `json:"position_x"`
	PositionY   int    `json:"position_y"`
	DisplayName string `json:"display_name"`
	Color       int    `json:"color"`
}

func sendJSON(v any) {
	if err := json.NewEncoder(os.Stdout).Encode(v); err != nil {
		fmt.Fprintln(os.Stderr, "Error encoding response:", err)
	}
}

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println(("No .env file found, using environment variables"))
	}

	dsn := os.Getenv("MYSQL_DSN")
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatal("Error connecting to database:", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatal("Error connecting to database:", err)
	}

	scanner := bufio.NewScanner(os.Stdin)
	fmt.Fprintln(os.Stderr, "Waiting for commands on stdin...")

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		var req Command
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			fmt.Fprintln(os.Stderr, "Invalid command payload:", err)
			continue
		}

		switch req.Command {
		case "fetch_players":
			players, err := FetchPlayers(db, req.ServerID)
			if err != nil {
				fmt.Fprintln(os.Stderr, "Error fetching players:", err)
				continue
			}
			sendJSON(players)

		case "fetch_player":
			player, err := FetchPlayer(db, req.ServerID, req.MemberID)
			if err != nil {
				fmt.Fprintln(os.Stderr, "Error fetching player:", err)
				continue
			}
			sendJSON(player)

		case "insert_player":
			displayName := req.DisplayName
			player := Players{
				ServerID:     req.ServerID,
				MemberID:     req.MemberID,
				Position_X:   req.PositionX,
				Position_Y:   req.PositionY,
				Display_Name: &displayName,
				Color:        req.Color,
			}
			if err := InsertPlayer(db, player); err != nil {
				fmt.Fprintln(os.Stderr, "Error inserting player:", err)
				continue
			}
			sendJSON(map[string]bool{"ok": true})

		case "update_player":
			displayName := req.DisplayName
			player := Players{
				ServerID:     req.ServerID,
				MemberID:     req.MemberID,
				Position_X:   req.PositionX,
				Position_Y:   req.PositionY,
				Display_Name: &displayName,
				Color:        req.Color,
			}
			if err := UpdatePlayer(db, player); err != nil {
				fmt.Fprintln(os.Stderr, "Error updating player:", err)
				continue
			}
			sendJSON(map[string]bool{"ok": true})

		case "delete_player":
			if err := DeletePlayer(db, req.ServerID, req.MemberID); err != nil {
				fmt.Fprintln(os.Stderr, "Error deleting player:", err)
				continue
			}
			sendJSON(map[string]bool{"ok": true})

		default:
			fmt.Fprintln(os.Stderr, "Unknown command:", req.Command)
		}
	}

	if err := scanner.Err(); err != nil {
		log.Println("Error reading stdin:", err)
	}
}
