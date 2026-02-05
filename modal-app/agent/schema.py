 """
 Excel schema analysis using Claude.
 
 Dynamically understands the structure of Excel files to determine
 what data needs to be updated.
 """
 
 import os
 from pathlib import Path
 from typing import Any
 import openpyxl
 from openpyxl.utils import get_column_letter
 
 
 def analyze_excel_file(file_path: Path) -> dict[str, Any]:
     """
     Analyze an Excel file and extract its structure.
     
     Args:
         file_path: Path to the Excel file
     
     Returns:
         Dict containing sheet names, headers, sample data, and empty cells
     """
     try:
         workbook = openpyxl.load_workbook(file_path, data_only=True)
         
         analysis = {
             "file_name": file_path.name,
             "sheets": [],
         }
         
         for sheet_name in workbook.sheetnames:
             sheet = workbook[sheet_name]
             sheet_info = {
                 "name": sheet_name,
                 "dimensions": sheet.dimensions,
                 "max_row": sheet.max_row,
                 "max_col": sheet.max_column,
                 "headers": [],
                 "sample_data": [],
                 "empty_cells": [],
             }
             
             # Get headers (first row)
             if sheet.max_row >= 1:
                 for col in range(1, min(sheet.max_column + 1, 20)):  # Limit to 20 columns
                     cell = sheet.cell(row=1, column=col)
                     if cell.value:
                         sheet_info["headers"].append({
                             "column": get_column_letter(col),
                             "value": str(cell.value)[:100],  # Truncate long headers
                         })
             
             # Get sample data (first 5 data rows)
             for row in range(2, min(sheet.max_row + 1, 7)):
                 row_data = {}
                 for col in range(1, min(sheet.max_column + 1, 20)):
                     cell = sheet.cell(row=row, column=col)
                     col_letter = get_column_letter(col)
                     
                     if cell.value is not None:
                         row_data[col_letter] = str(cell.value)[:50]
                     else:
                         # Track empty cells that might need data
                         sheet_info["empty_cells"].append(f"{col_letter}{row}")
                 
                 if row_data:
                     sheet_info["sample_data"].append(row_data)
             
             # Look for cells that might need updating (empty cells in data area)
             # Only sample a subset to avoid overwhelming the context
             empty_count = 0
             for row in range(2, min(sheet.max_row + 1, 50)):
                 for col in range(1, min(sheet.max_column + 1, 20)):
                     cell = sheet.cell(row=row, column=col)
                     if cell.value is None:
                         col_letter = get_column_letter(col)
                         if len(sheet_info["empty_cells"]) < 50:
                             if f"{col_letter}{row}" not in sheet_info["empty_cells"]:
                                 sheet_info["empty_cells"].append(f"{col_letter}{row}")
                         empty_count += 1
             
             sheet_info["total_empty_cells"] = empty_count
             analysis["sheets"].append(sheet_info)
         
         workbook.close()
         return analysis
         
     except Exception as e:
         return {"error": str(e), "file_name": file_path.name}
 
 
 def analyze_all_files(files: dict[str, Path]) -> dict[str, dict]:
     """
     Analyze all Excel files for a ticker.
     
     Args:
         files: Dict mapping bucket names to local file paths
     
     Returns:
         Dict mapping bucket names to analysis results
     """
     analyses = {}
     
     for bucket_name, file_path in files.items():
         if file_path.exists():
             analyses[bucket_name] = analyze_excel_file(file_path)
         else:
             analyses[bucket_name] = {"error": "File not found", "file_name": file_path.name}
     
     return analyses
 
 
 def format_schema_for_llm(analyses: dict[str, dict]) -> str:
     """
     Format the schema analysis as a string for the LLM context.
     
     Args:
         analyses: Dict of analysis results per file
     
     Returns:
         Formatted string describing all file schemas
     """
     output = []
     
     for bucket_name, analysis in analyses.items():
         output.append(f"\n## File: {bucket_name}")
         
         if "error" in analysis:
             output.append(f"  Error: {analysis['error']}")
             continue
         
         for sheet in analysis.get("sheets", []):
             output.append(f"\n  ### Sheet: {sheet['name']}")
             output.append(f"  Dimensions: {sheet['dimensions']} ({sheet['max_row']} rows x {sheet['max_col']} cols)")
             
             if sheet["headers"]:
                 header_str = ", ".join([f"{h['column']}: {h['value']}" for h in sheet["headers"]])
                 output.append(f"  Headers: {header_str}")
             
             if sheet["sample_data"]:
                 output.append("  Sample data:")
                 for i, row in enumerate(sheet["sample_data"][:3], start=2):
                     row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                     output.append(f"    Row {i}: {row_str}")
             
             if sheet["empty_cells"]:
                 output.append(f"  Empty cells (sample): {', '.join(sheet['empty_cells'][:20])}")
                 if sheet["total_empty_cells"] > 20:
                     output.append(f"  (Total empty cells: {sheet['total_empty_cells']})")
     
     return "\n".join(output)