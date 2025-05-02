# database.py - Includes Workflows Table and Methods (Verified)

import sqlite3
import os
import json # For handling steps list serialization
from datetime import datetime # For potential future use with timestamps

class DatabaseManager:
    """
    Manages the SQLite database for storing prompts and workflows.
    Handles connection, table creation, and CRUD operations.
    """
    def __init__(self, db_name="prompts.db"):
        """
        Initializes the DatabaseManager. Connects to the database and ensures
        all necessary tables ('prompts', 'workflows') exist and have the
        correct schema.
        """
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        print(f"Initializing DatabaseManager for '{self.db_name}'")
        self._connect()
        if self.connection:
            self._create_prompts_table()
            self._create_workflows_table()

    def _connect(self):
        """Establishes a connection to the SQLite database file."""
        try:
            # check_same_thread=False is needed if using the DB connection from multiple threads
            self.connection = sqlite3.connect(self.db_name, check_same_thread=False)
            self.cursor = self.connection.cursor()
            print(f"Database connection successful: {self.db_name}")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            self.connection = None
            self.cursor = None

    def _table_exists(self, table_name: str) -> bool:
        """Checks if a table exists in the database."""
        if not self.cursor:
            return False
        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
            return self.cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"Error checking if table {table_name} exists: {e}")
            return False

    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        """Checks if a table has a specific column."""
        if not self.cursor:
            return False
        try:
            # Use PRAGMA to get table information
            self.cursor.execute(f"PRAGMA table_info(`{table_name}`);") # Use backticks for safety
            columns = [info[1] for info in self.cursor.fetchall()] # Column name is at index 1 in pragma result
            return column_name in columns
        except sqlite3.Error as e:
            print(f"Error checking column '{column_name}' in '{table_name}': {e}")
            return False

    def _add_output_variable_column_to_prompts(self):
        """Adds the output_variable_name column to prompts table if it doesn't exist (for migration)."""
        table = "prompts"
        column = "output_variable_name"
        if not self._table_exists(table):
            # This shouldn't happen if _create_prompts_table runs first, but check anyway
            print(f"Table '{table}' does not exist, cannot add column '{column}'.")
            return False
        if self._table_has_column(table, column):
            return True # Column already exists

        # Attempt to add the column
        try:
            print(f"Attempting to add column '{column}' to '{table}' table...")
            self.cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` TEXT;")
            self.connection.commit()
            print(f"Column '{column}' added successfully.")
            return True
        except sqlite3.Error as e:
            print(f"Error adding column '{column}' to '{table}': {e}")
            self.connection.rollback()
            return False

    def _create_prompts_table(self):
        """Creates the 'prompts' table if it doesn't exist and ensures schema."""
        if not self.cursor:
            print("Cannot create prompts table: No database cursor.")
            return
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_text TEXT NOT NULL,
                category TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                output_variable_name TEXT -- For prompt chaining output variable
            );
            """
            self.cursor.execute(create_table_sql)
            self.connection.commit()
            print("Table 'prompts' checked/created.")
            # Ensure the output variable column exists, even if table was created before
            self._add_output_variable_column_to_prompts()
        except sqlite3.Error as e:
            print(f"Error creating/checking 'prompts' table: {e}")

    def _create_workflows_table(self):
        """Creates the 'workflows' table if it doesn't exist."""
        if not self.cursor:
            print("Cannot create workflows table: No database cursor.")
            return
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,       -- Ensure workflow names are unique
                description TEXT,
                steps_json TEXT DEFAULT '[]'    -- Store list of prompt IDs as JSON array string
            );
            """
            self.cursor.execute(create_table_sql)
            # Optional: Index on name for faster lookup/uniqueness enforcement
            self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_name ON workflows (name);")
            self.connection.commit()
            print("Table 'workflows' checked/created.")
        except sqlite3.Error as e:
            print(f"Error creating/checking 'workflows' table: {e}")

    # --- Prompts Methods ---

    def add_prompt(self, prompt_text: str, category: str | None = None, notes: str | None = None, output_variable_name: str | None = None) -> int | None:
        if not prompt_text or not self.connection or not self.cursor:
            return None
        sql = "INSERT INTO prompts (prompt_text, category, notes, output_variable_name) VALUES (?, ?, ?, ?);"
        try:
            self.cursor.execute(sql, (prompt_text, category, notes, output_variable_name));
            self.connection.commit();
            last_id = self.cursor.lastrowid;
            print(f"Prompt added ID: {last_id}");
            return last_id
        except sqlite3.Error as e:
            print(f"DB Error add_prompt: {e}");
            self.connection.rollback();
            return None

    def update_prompt(self, prompt_id: int, prompt_text: str, category: str | None = None, notes: str | None = None, output_variable_name: str | None = None) -> bool:
        if prompt_id is None or not prompt_text or not self.connection or not self.cursor: # Added check for prompt_id being None
            return False
        sql = "UPDATE prompts SET prompt_text = ?, category = ?, notes = ?, output_variable_name = ? WHERE id = ?;"
        try:
            self.cursor.execute(sql, (prompt_text, category, notes, output_variable_name, prompt_id));
            rows = self.cursor.rowcount;
            self.connection.commit();
            if rows > 0:
                print(f"Prompt ID {prompt_id} updated.");
                return True
            else:
                print(f"Warning: Prompt ID {prompt_id} not found for update.");
                return False
        except sqlite3.Error as e:
            print(f"DB Error update_prompt ID {prompt_id}: {e}");
            self.connection.rollback();
            return False

    def get_all_prompts(self) -> list[tuple]:
        if not self.cursor:
            print("Error: No DB cursor for get_all_prompts.");
            return []
        try:
            sql = "SELECT id, prompt_text, category, notes, created_at, output_variable_name FROM prompts ORDER BY created_at DESC;";
            self.cursor.execute(sql);
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"DB Error get_all_prompts: {e}");
            return []

    def get_prompts_by_category(self, category: str | None) -> list[tuple]:
        if not self.cursor:
            print("Error: No DB cursor for get_prompts_by_category.");
            return []
        try:
            if category is None:
                sql = "SELECT id, prompt_text, category, notes, created_at, output_variable_name FROM prompts WHERE category IS NULL ORDER BY created_at DESC;";
                self.cursor.execute(sql)
            else:
                sql = "SELECT id, prompt_text, category, notes, created_at, output_variable_name FROM prompts WHERE category = ? ORDER BY created_at DESC;";
                self.cursor.execute(sql, (category,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"DB Error get_prompts_by_category '{category}': {e}");
            return []

    def get_prompt_by_id(self, prompt_id: int) -> tuple | None:
        if not self.cursor or prompt_id is None:
            print("Error: No cursor or invalid ID for get_prompt_by_id.");
            return None
        try:
            sql = "SELECT id, prompt_text, category, notes, created_at, output_variable_name FROM prompts WHERE id = ?;";
            self.cursor.execute(sql, (prompt_id,));
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"DB Error get_prompt_by_id {prompt_id}: {e}");
            return None

    def get_unique_categories(self) -> list[str | None]:
        if not self.cursor:
            print("Error: No DB cursor for get_unique_categories.");
            return []
        try:
            # Order NULLs first, then by category name case-insensitively
            sql = "SELECT DISTINCT category FROM prompts ORDER BY CASE WHEN category IS NULL THEN 0 ELSE 1 END, category COLLATE NOCASE ASC;";
            self.cursor.execute(sql);
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"DB Error get_unique_categories: {e}");
            return []

    def delete_prompt(self, prompt_id: int) -> bool:
        if not self.cursor or prompt_id is None:
            print("Error: No cursor or invalid ID for delete_prompt.");
            return False
        try:
            sql = "DELETE FROM prompts WHERE id = ?;";
            self.cursor.execute(sql, (prompt_id,));
            rows = self.cursor.rowcount;
            self.connection.commit();
            if rows > 0:
                print(f"Prompt ID {prompt_id} deleted.");
                return True
            else:
                print(f"Warning: Prompt ID {prompt_id} not found for deletion.");
                return False
        except sqlite3.Error as e:
            print(f"DB Error delete_prompt ID {prompt_id}: {e}");
            self.connection.rollback();
            return False

    # --- Workflow Methods ---

    def add_workflow(self, name: str, description: str = "") -> int | None:
        """Adds a new workflow. Returns new ID or None on failure/duplicate."""
        if not name or not self.connection or not self.cursor:
            print("Error: Cannot add workflow. Missing name or DB connection."); # Added more context
            return None
        sql = "INSERT INTO workflows (name, description) VALUES (?, ?);"
        try:
            self.cursor.execute(sql, (name, description));
            self.connection.commit();
            new_id = self.cursor.lastrowid;
            print(f"Workflow '{name}' added ID: {new_id}");
            return new_id
        except sqlite3.IntegrityError:
            print(f"Error: Workflow name '{name}' exists.");
            self.connection.rollback();
            return None
        except sqlite3.Error as e:
            print(f"Error adding workflow '{name}': {e}");
            self.connection.rollback();
            return None

    def update_workflow_steps(self, workflow_id: int, steps_list: list[int]) -> bool:
        """Updates the steps JSON for a given workflow ID."""
        if workflow_id is None or not self.connection or not self.cursor:
            print("Error: Cannot update workflow steps. Missing ID or DB connection."); # Added context
            return False
        try:
            steps_json = json.dumps(steps_list);
            sql = "UPDATE workflows SET steps_json = ? WHERE id = ?;";
            self.cursor.execute(sql, (steps_json, workflow_id));
            rows = self.cursor.rowcount;
            self.connection.commit();
            if rows > 0:
                print(f"Workflow ID {workflow_id} steps updated.");
                return True
            else:
                print(f"Warning: Workflow ID {workflow_id} not found for step update.");
                return False # Not found != success
        except sqlite3.Error as e:
            print(f"Error updating steps WF ID {workflow_id}: {e}");
            self.connection.rollback();
            return False
        except TypeError as e:
            print(f"Error encoding steps list: {e}"); # Added context
            return False
        except Exception as e: # Catch potential other issues during json.dumps
             print(f"Unexpected error updating steps WF ID {workflow_id}: {e}");
             self.connection.rollback();
             return False

    def delete_workflow(self, workflow_id: int) -> bool:
        """Deletes a workflow by ID."""
        if not self.cursor or workflow_id is None:
            print("Error: Cannot delete workflow. Missing cursor or invalid ID."); # Added context
            return False
        try:
            sql = "DELETE FROM workflows WHERE id = ?;";
            self.cursor.execute(sql, (workflow_id,));
            rows = self.cursor.rowcount;
            self.connection.commit();
            if rows > 0:
                print(f"Workflow ID {workflow_id} deleted.");
                return True
            else:
                print(f"Warning: Workflow ID {workflow_id} not found for deletion.");
                return False
        except sqlite3.Error as e:
            print(f"Error deleting workflow ID {workflow_id}: {e}");
            self.connection.rollback();
            return False

    def get_all_workflows(self) -> list[tuple]:
        """Retrieves all workflows (id, name, description), ordered by name."""
        if not self.cursor:
            print("Error: No DB cursor for get_all_workflows.");
            return []
        try:
            sql = "SELECT id, name, description FROM workflows ORDER BY name COLLATE NOCASE ASC;";
            self.cursor.execute(sql);
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error retrieving workflows: {e}");
            return []

    def get_workflow_steps(self, workflow_id: int) -> list[int] | None:
        """Retrieves the list of prompt IDs for a workflow."""
        if not self.cursor or workflow_id is None:
            print("Error: Cannot get workflow steps. Missing cursor or invalid ID."); # Added context
            return None
        try:
            sql = "SELECT steps_json FROM workflows WHERE id = ?;";
            self.cursor.execute(sql, (workflow_id,));
            result = self.cursor.fetchone();
            if result and result[0]: # Check if row and json string exist
                steps_list = json.loads(result[0]) # Parse JSON string from the first (and only) column
                # Basic validation: check if it's a list and contains only integers
                if isinstance(steps_list, list) and all(isinstance(item, int) for item in steps_list):
                    return steps_list
                else:
                    print(f"Warning: Invalid steps_json format for Workflow ID {workflow_id}. Data: {result[0]}"); # Log problematic data
                    return [] # Corrupt data, treat as empty list of steps
            else:
                return [] # No steps defined ('[]' default) or workflow ID not found
        except json.JSONDecodeError as e:
            print(f"Error decoding steps_json for Workflow ID {workflow_id}: {e}");
            return None # Indicate an error occurred trying to read the steps
        except sqlite3.Error as e:
            print(f"Error getting steps for Workflow ID {workflow_id}: {e}");
            return None
        except Exception as e: # Catch unexpected errors during processing
             print(f"Unexpected error getting steps for Workflow ID {workflow_id}: {e}");
             return None


    # --- Cleanup ---
    def close_connection(self):
        """Closes the database connection."""
        if self.connection is not None:
            try:
                self.connection.close();
                print("Database connection closed.");
                self.connection = None;
                self.cursor = None
            except sqlite3.Error as e:
                print(f"Error closing DB connection: {e}")

# Example usage (for direct testing)
if __name__ == "__main__":
    print("\n--- Running database.py tests ---");
    test_db_name = "test_db_workflows_v2.db";
    if os.path.exists(test_db_name):
        os.remove(test_db_name);
        print(f"Removed {test_db_name}")
    dbm = DatabaseManager(db_name=test_db_name)
    if dbm.connection:
        print("\nTesting prompts...");
        p1 = dbm.add_prompt("T1 {in}", output_variable_name="t1_out");
        p2 = dbm.add_prompt("T2 {t1_out}", output_variable_name="t2_out");
        p3 = dbm.add_prompt("T3 {t2_out}"); # No output variable
        if not all([p1, p2, p3]):
            print("ERR: Failed to add prompts");
            #exit() # Don't exit, continue testing workflows

        print("\nTesting workflows...");
        print("1. Add WFs...");
        wf1 = dbm.add_workflow("WF_A");
        wf2 = dbm.add_workflow("WF_B", "Desc B");
        if not all([wf1, wf2]):
             print("ERR: Failed to add workflows");
             #exit() # Don't exit, continue testing

        print("\n2. Get WFs...");
        all_wfs = dbm.get_all_workflows()
        print(f"Found: {all_wfs}")
        if len(all_wfs) != 2: print("WARN: Incorrect number of workflows found.")

        print(f"\n3. Update steps WF {wf1}");
        success = dbm.update_workflow_steps(wf1, [p1, p2, p3]);
        print(f"Update ok: {success}");
        if not success: print(f"ERR: Failed to update steps for WF {wf1}")

        print(f"\n4. Get steps WF {wf1}");
        steps = dbm.get_workflow_steps(wf1)
        print(f"Steps: {steps}")
        if steps != [p1, p2, p3]: print(f"WARN: Steps mismatch for WF {wf1}. Expected {[p1, p2, p3]}, got {steps}")

        print(f"\n5. Delete WF {wf2}");
        print(f"Delete ok: {dbm.delete_workflow(wf2)}");
        all_wfs_after_delete = dbm.get_all_workflows()
        print(f"WFs after: {all_wfs_after_delete}")
        if len(all_wfs_after_delete) != 1 or (all_wfs_after_delete and all_wfs_after_delete[0][0] != wf1):
             print("WARN: Workflow delete failed or list incorrect.")


        print("\n6. Add duplicate WF...");
        add_duplicate_result = dbm.add_workflow("WF_A")
        print(f"Result: {add_duplicate_result}")
        if add_duplicate_result is not None: print("WARN: Added duplicate workflow unexpectedly.")

        print("\n7. Get steps for non-existent WF...");
        print(f"Result: {dbm.get_workflow_steps(999)}") # Assume 999 doesn't exist

        print("\n8. Update steps for non-existent WF...");
        print(f"Result: {dbm.update_workflow_steps(999, [p1])}")

        print("\n9. Delete non-existent WF...");
        print(f"Result: {dbm.delete_workflow(999)}")

        dbm.close_connection()
    else:
        print("DB connection failed. Cannot run tests.")
    print("\n--- Database tests complete ---")