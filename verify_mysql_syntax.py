#!/usr/bin/env python3
"""
Verification script to confirm ItemListModule uses correct MySQL syntax.
This script validates that all SQL queries use %s placeholders and correct column names.
"""
import re
from pathlib import Path

def check_mysql_syntax(file_path):
    """Check if file uses MySQL syntax (%s) instead of SQLite (?)"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Extract all SQL query blocks (text between """ or ''')
    sql_blocks = re.findall(r'"""(.*?)"""', content, re.DOTALL)
    sql_blocks.extend(re.findall(r"'''(.*?)'''", content, re.DOTALL))

    issues = []

    # Check for SQLite placeholders in SQL blocks
    for block in sql_blocks:
        if '?' in block:
            issues.append(f"  ✗ SQLite placeholder (?) found in SQL query")

    # Check for old column name in SQL blocks (in SELECT, WHERE, INSERT context only)
    for block in sql_blocks:
        # Look for item_name in SQL contexts (SELECT/INSERT columns, WHERE clauses)
        if re.search(r'(SELECT|INSERT INTO.*\().*\bitem_name\b', block, re.IGNORECASE | re.DOTALL):
            issues.append(f"  ✗ Old column 'item_name' in SELECT/INSERT (should be 'name')")
        if re.search(r'WHERE.*\bitem_name\b', block, re.IGNORECASE):
            issues.append(f"  ✗ Old column 'item_name' in WHERE clause (should be 'name')")

    # Count correct patterns
    correct = []

    # Count %s placeholders in SQL blocks
    total_placeholders = sum(block.count('%s') for block in sql_blocks)
    if total_placeholders > 0:
        correct.append(f"  ✓ MySQL placeholders (%s): {total_placeholders} occurrence(s)")

    # Count uses of 'name' column in SQL blocks
    name_count = sum(1 for block in sql_blocks if re.search(r'\bname\b', block, re.IGNORECASE))
    if name_count > 0:
        correct.append(f"  ✓ Correct column 'name' in SQL: {name_count} query/queries")

    # Check for negative quantity validation
    if 'if new_quantity < 0:' in content:
        correct.append(f"  ✓ Negative quantity prevention in update_quantity()")
    if 'if quantity < 0:' in content:
        correct.append(f"  ✓ Negative quantity prevention in set_quantity()")

    return issues, correct

def main():
    print("\n" + "="*70)
    print("MySQL SYNTAX VERIFICATION")
    print("="*70 + "\n")

    module_path = Path("/data/AssistantStudies/modules/item_list.py")

    print(f"Checking: {module_path}\n")

    issues, correct = check_mysql_syntax(module_path)

    if correct:
        print("✓ CORRECT PATTERNS FOUND:")
        for item in correct:
            print(item)
        print()

    if issues:
        print("✗ ISSUES FOUND:")
        for item in issues:
            print(item)
        print("\n" + "="*70)
        print("STATUS: FAILED - Fix issues above")
        print("="*70 + "\n")
        return 1
    else:
        print("="*70)
        print("STATUS: PASSED - All fixes applied correctly")
        print("="*70 + "\n")
        return 0

if __name__ == '__main__':
    exit(main())
