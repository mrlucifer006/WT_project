import csv
import os
from datetime import datetime
from typing import List, Dict

class CSVService:
    def __init__(self, file_path: str = "transactions.csv"):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Header: Timestamp, Name, Phone, Entry ID, Duration, Status, Entry Type
                writer.writerow([
                    "Timestamp", "Name", "Phone", "Entry ID", 
                    "Duration", "Status", "Entry Type"
                ])

    def append_data(self, data: List[str]):
        """Appends a row of entry data to the CSV."""
        self._ensure_file_exists()
        try:
            with open(self.file_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(data)
            print(f"Successfully appended entry to CSV: {data}")
        except Exception as e:
            print(f"Error appending data to CSV: {e}")

    def fetch_data(self) -> List[Dict]:
        self._ensure_file_exists()
        try:
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            print(f"Error fetching data: {e}")
            return []

    def check_transaction_exists(self, transaction_id: str) -> bool:
        """Checks if an Entry ID already exists in the CSV."""
        self._ensure_file_exists()
        try:
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                for row in reader:
                    if len(row) > 3 and row[3].strip() == transaction_id.strip():
                        return True
            return False
        except Exception as e:
            print(f"Error checking entry existence: {e}")
            return False

    def update_entry_status(self, transaction_id: str, new_status: str):
        """Updates the status (Column 5, index 5) of a specific entry based on Entry ID."""
        self._ensure_file_exists()
        try:
            rows = []
            updated = False
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if headers:
                    rows.append(headers)
                for row in reader:
                    if len(row) > 3 and row[3].strip() == transaction_id.strip():
                        if len(row) > 5:
                            row[5] = new_status
                        updated = True
                    rows.append(row)
            
            if updated:
                with open(self.file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                print(f"Updated status for {transaction_id} to {new_status}")
                return True
            else:
                print(f"Entry ID {transaction_id} not found.")
                return False
                
        except Exception as e:
            print(f"Error updating status: {e}")
            return False

    def get_stats_for_today(self, *args, **kwargs):
        """Calculates total entries for the current day."""
        self._ensure_file_exists()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            count = 0

            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    timestamp = row[0]
                    if timestamp.startswith(today_str):
                        count += 1
                            
            return {"count": count, "total": count}
        except Exception as e:
            print(f"Error calculating daily stats: {e}")
            return {"count": 0, "total": 0}

    def get_total_stats(self, *args, **kwargs):
        """Calculates all-time total entries."""
        self._ensure_file_exists()
        try:
            count = 0

            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    count += 1
                        
            return {"count": count, "total": count}
        except Exception as e:
            print(f"Error calculating total stats: {e}")
            return {"count": 0, "total": 0}

    def get_entry_status(self, transaction_id: str) -> str:
        """Gets the current status of an Entry ID."""
        self._ensure_file_exists()
        try:
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                for row in reader:
                    if len(row) > 5 and row[3].strip() == transaction_id.strip():
                        return row[5]
            return None
        except Exception as e:
            print(f"Error getting status: {e}")
            return None

    def clear_data(self) -> bool:
        """Wipes the CSV file and resets the header row."""
        try:
            with open(self.file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Name", "Phone", "Entry ID", 
                    "Duration", "Status", "Entry Type"
                ])
            print("CSV database cleared and reset.")
            return True
        except Exception as e:
            print(f"Error clearing CSV database: {e}")
            return False

csv_service = CSVService()
