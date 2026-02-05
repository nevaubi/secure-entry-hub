 """
 Excel file updater using openpyxl.
 
 Handles updating specific cells in Excel files based on AI instructions.
 """
 
 from pathlib import Path
 from typing import Any
 import openpyxl
 from openpyxl.utils import column_index_from_string
 
 
 class ExcelUpdater:
     """Updates Excel files based on AI instructions."""
     
     def __init__(self, file_path: Path):
         self.file_path = file_path
         self.workbook = openpyxl.load_workbook(file_path)
         self.changes_made = 0
     
     def update_cell(self, sheet_name: str, cell_ref: str, value: Any) -> bool:
         """
         Update a specific cell in the workbook.
         
         Args:
             sheet_name: Name of the sheet
             cell_ref: Cell reference like "A1" or "B5"
             value: Value to set
         
         Returns:
             True if successful, False otherwise
         """
         try:
             if sheet_name not in self.workbook.sheetnames:
                 print(f"Sheet '{sheet_name}' not found")
                 return False
             
             sheet = self.workbook[sheet_name]
             sheet[cell_ref] = value
             self.changes_made += 1
             print(f"Updated {sheet_name}!{cell_ref} = {value}")
             return True
             
         except Exception as e:
             print(f"Error updating cell {sheet_name}!{cell_ref}: {e}")
             return False
     
     def update_cells_batch(self, updates: list[dict]) -> int:
         """
         Update multiple cells at once.
         
         Args:
             updates: List of dicts with keys: sheet_name, cell_ref, value
         
         Returns:
             Number of successful updates
         """
         successful = 0
         for update in updates:
             if self.update_cell(
                 update["sheet_name"],
                 update["cell_ref"],
                 update["value"]
             ):
                 successful += 1
         return successful
     
     def save(self) -> bool:
         """
         Save the workbook.
         
         Returns:
             True if successful, False otherwise
         """
         try:
             self.workbook.save(self.file_path)
             print(f"Saved {self.file_path} with {self.changes_made} changes")
             return True
         except Exception as e:
             print(f"Error saving {self.file_path}: {e}")
             return False
     
     def close(self):
         """Close the workbook."""
         self.workbook.close()
     
     def __enter__(self):
         return self
     
     def __exit__(self, exc_type, exc_val, exc_tb):
         self.close()
 
 
 def update_file(file_path: Path, updates: list[dict]) -> tuple[bool, int]:
     """
     Convenience function to update a file with multiple changes.
     
     Args:
         file_path: Path to the Excel file
         updates: List of cell updates
     
     Returns:
         Tuple of (success, number of changes)
     """
     with ExcelUpdater(file_path) as updater:
         count = updater.update_cells_batch(updates)
         if count > 0:
             success = updater.save()
             return success, count
         return True, 0