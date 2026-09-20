package main

import (
	"database/sql"
)

type Players struct {
	ServerID     int     `json:"server_id"`
	MemberID     int     `json:"member_id"`
	Position_X   int     `json:"position_x"`
	Position_Y   int     `json:"position_y"`
	Display_Name *string `json:"display_name"`
	Color        int     `json:"color"`
}

func FetchPlayers(db *sql.DB, serverID int) ([]Players, error) {
	rows, err := db.Query("SELECT server_id, member_id, position_x, position_y, display_name, color FROM player_list WHERE server_id = ?", serverID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var players []Players
	for rows.Next() {
		var player Players
		if err := rows.Scan(&player.ServerID, &player.MemberID, &player.Position_X, &player.Position_Y, &player.Display_Name, &player.Color); err != nil {
			return nil, err
		}
		players = append(players, player)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return players, nil
}

func FetchPlayer(db *sql.DB, serverID int, memberID int) (*Players, error) {
	row := db.QueryRow("SELECT server_id, member_id, position_x, position_y, display_name, color FROM player_list WHERE server_id = ? AND member_id = ?", serverID, memberID)
	var player Players
	if err := row.Scan(&player.ServerID, &player.MemberID, &player.Position_X, &player.Position_Y, &player.Display_Name, &player.Color); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil // No player found
		}
		return nil, err
	}
	return &player, nil
}

func InsertPlayer(db *sql.DB, player Players) error {
	_, err := db.Exec("INSERT INTO player_list (server_id, member_id, position_x, position_y, display_name, color) VALUES (?, ?, ?, ?, ?, ?)",
		player.ServerID, player.MemberID, player.Position_X, player.Position_Y, player.Display_Name, player.Color)
	return err
}

func UpdatePlayer(db *sql.DB, player Players) error {
	res, err := db.Exec("UPDATE player_list SET position_x = ?, position_y = ?, display_name = ?, color = ? WHERE server_id = ? AND member_id = ?",
		player.Position_X, player.Position_Y, player.Display_Name, player.Color, player.ServerID, player.MemberID)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return sql.ErrNoRows
	}
	return nil
}

func DeletePlayer(db *sql.DB, serverID int, memberID int) error {
	res, err := db.Exec("DELETE FROM player_list WHERE server_id = ? AND member_id = ?", serverID, memberID)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return sql.ErrNoRows
	}
	return nil
}
