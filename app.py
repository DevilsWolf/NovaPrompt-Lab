# app.py - Updated with Full Guide Integration

# --- Keep all imports ---
import sys
import requests # Used only for model fetching now
import json
import os
import urllib.parse
import traceback
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QListWidget, QSplitter, QLabel,
                             QMessageBox, QListWidgetItem, QProgressDialog,
                             QLineEdit, QComboBox, QFormLayout,
                             QDoubleSpinBox, QSpinBox,
                             QGroupBox, QScrollArea, QTabWidget,
                             QInputDialog, QAbstractItemView, QDialog,
                             QDialogButtonBox, QDockWidget) # Add Dialog imports
from PyQt6 import QtCore
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QTextCursor, QAction, QKeySequence
# --- End Imports ---

try:
    from database import DatabaseManager
    from ui import Ui_MainWindow
    from workers import WorkerThread, WorkflowRunner, VARIABLE_PATTERN
except ImportError as e:
    print(f"CRITICAL ERROR: Missing required file ({e.name}).") # ... (rest of error handling) ...
    app_temp = QApplication.instance();
    if not app_temp:
        app_temp = QApplication(sys.argv)
    error_box = QMessageBox();
    error_box.setIcon(QMessageBox.Icon.Critical);
    error_box.setWindowTitle("Startup Error")
    error_box.setText(f"CRITICAL ERROR: Required file missing ({e.name}).\n\nPlease ensure database.py, ui.py, and workers.py are in the same directory.")
    error_box.exec();
    sys.exit(1)


# --- Constants and Config (Same) ---
LM_STUDIO_API_BASE_URL = "http://localhost:1234/v1";
DEFAULT_MODEL_FALLBACK = "No models loaded/found";
DEFAULT_TEMPERATURE = 0.7;
DEFAULT_MAX_TOKENS = 1024;
VARIABLE_UPDATE_DEBOUNCE_MS = 350

# --- WorkflowInputDialog Class (Keep As Is) ---
class WorkflowInputDialog(QDialog):
    # ... (Keep the full class definition from the previous step) ...
    def __init__(self, required_vars: list[str], parent=None):
        super().__init__(parent);
        self.setWindowTitle("Workflow Input Required");
        self.setMinimumWidth(400);
        self.setWindowModality(Qt.WindowModality.WindowModal);
        self.layout = QVBoxLayout(self);
        self.form_layout = QFormLayout();
        self.input_widgets: dict[str, QLineEdit] = {}
        if not required_vars:
            self.layout.addWidget(QLabel("No initial input variables required."))
        else:
            intro_label = QLabel("Provide values for initial workflow variables:");
            self.layout.addWidget(intro_label);
            for var_name in required_vars:
                line_edit = QLineEdit(self);
                line_edit.setPlaceholderText(f"Value for {{{var_name}}}...");
                self.input_widgets[var_name] = line_edit;
                self.form_layout.addRow(f"{var_name}:", line_edit)
        self.layout.addLayout(self.form_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel);
        self.button_box.accepted.connect(self.accept);
        self.button_box.rejected.connect(self.reject);
        self.layout.addWidget(self.button_box)
        if self.input_widgets:
            first_widget = next(iter(self.input_widgets.values()));
            QTimer.singleShot(0, first_widget.setFocus)
    def get_values(self) -> dict[str, str] | None:
        values = {};
        missing = [];
        for var_name, widget in self.input_widgets.items():
            value = widget.text().strip();
            if not value:
                missing.append(var_name)
            else:
                values[var_name] = value
        if missing:
            QMessageBox.warning(self, "Input Missing", f"Provide values for:\n- {chr(10).join(missing)}");
            return None
        return values

# --- MainWindow Class ---
class MainWindow(QMainWindow):
    # --- __init__ (Same) ---
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent);
        print("--- MainWindow __init__ started ---")
        self.setWindowTitle("NovaPrompt Lab");
        self.setGeometry(100, 100, 1200, 850);
        self.variable_inputs: dict[str, QLineEdit] = {};
        self.db_manager = DatabaseManager();
        self.progress_dialog: QProgressDialog | None = None;
        self.current_prompt_id: int | None = None;
        self.worker_thread: WorkerThread | None = None;
        self.workflow_runner: WorkflowRunner | None = None
        self.variable_update_timer = QTimer(self);
        self.variable_update_timer.setSingleShot(True);
        self.variable_update_timer.setInterval(VARIABLE_UPDATE_DEBOUNCE_MS);
        self.variable_update_timer.timeout.connect(self._perform_variable_update)
        self.workflows_data: list[tuple] = [];
        self.current_workflow_id: int | None = None;
        self.current_workflow_steps: list[int] = []
        self.ui = Ui_MainWindow();
        self.ui.setup_ui(self)
        self._create_workflow_log_dock() # Create dock before connecting signals potentially using it
        self._connect_signals();
        self._populate_category_filter();
        self._load_prompts_list();
        self._load_workflows_list();
        self._apply_stylesheet("style.qss")
        QTimer.singleShot(100, self._fetch_and_update_models);
        QTimer.singleShot(100, self._set_initial_splitter_sizes)
        print("--- MainWindow __init__ finished ---")

    # --- UI Setup Helpers (Referencing self.ui for widgets) ---
    def _create_workflow_log_dock(self): # Creates dock widget
        self.workflow_log_dock = QDockWidget("Workflow Log", self);
        self.workflow_log_dock.setObjectName("WorkflowLogDock");
        self.workflow_log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.workflow_log_output = QTextEdit();
        self.workflow_log_output.setReadOnly(True);
        self.workflow_log_output.setPlaceholderText("Workflow execution steps will appear here...");
        self.workflow_log_output.setObjectName("WorkflowLogOutput")
        self.workflow_log_dock.setWidget(self.workflow_log_output);
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.workflow_log_dock);
        self.workflow_log_dock.setVisible(False)
        view_menu = None; # Add toggle action to View menu
        for action in self.ui.menu_bar.actions(): # Access menu bar via self.ui
            if action.text() == "&View":
                view_menu = action.menu();
                break
        if not view_menu:
            view_menu = self.ui.menu_bar.addMenu("&View")
        toggle_log_action = self.workflow_log_dock.toggleViewAction();
        toggle_log_action.setText("Workflow &Log");
        toggle_log_action.setStatusTip("Show/Hide Workflow Log");
        view_menu.addAction(toggle_log_action)

    def _set_initial_splitter_sizes(self):
        print("--- _set_initial_splitter_sizes called ---");
        QTimer.singleShot(100, self._apply_splitter_sizes) # Delay slightly
    def _apply_splitter_sizes(self):
        try:
            main_width = self.ui.main_splitter.width();
            left_width = int(main_width * 0.3) if main_width > 50 else 350;
            right_width = main_width - left_width if main_width > 50 else 850;
            self.ui.main_splitter.setSizes([left_width, right_width]);
            right_height = self.ui.right_splitter.height();
            editor_height = int(right_height * 0.60) if right_height > 50 else 500;
            output_height = right_height - editor_height if right_height > 50 else 350;
            self.ui.right_splitter.setSizes([editor_height, output_height]);
            print(f"Applied main sizes: {[left_width, right_width]}");
            print(f"Applied right sizes: {[editor_height, output_height]}");
        except Exception as e:
            print(f"Warning: Splitter size failed: {e}")

    # --- Signal Connections (Add connection for Full Guide) --- <<< MODIFIED >>>
    def _connect_signals(self):
        print("--- _connect_signals started ---");
        # Access UI elements via self.ui.
        self.ui.category_filter_combo.currentIndexChanged.connect(self._filter_prompts_by_category);
        self.ui.search_input.textChanged.connect(self._filter_prompts_by_search);
        self.ui.prompt_list.itemClicked.connect(self._display_selected_prompt_preview);
        self.ui.load_button.clicked.connect(self._load_selected_prompt_to_editor);
        self.ui.delete_button.clicked.connect(self._delete_selected_prompt);
        self.ui.prompt_editor.textChanged.connect(self._on_prompt_text_changed); # Debounced variable update
        self.ui.save_button.clicked.connect(self._save_current_prompt);
        self.ui.clear_button.clicked.connect(self._clear_editor);
        self.ui.generate_button.clicked.connect(self._generate_prompt); # Single prompt generation
        self.ui.copy_output_button.clicked.connect(self._copy_output_to_editor);
        self.ui.refresh_models_button.clicked.connect(self._fetch_and_update_models);
        # Workflows Tab
        self.ui.new_workflow_button.clicked.connect(self._add_new_workflow);
        self.ui.delete_workflow_button.clicked.connect(self._delete_selected_workflow);
        self.ui.workflow_list.itemClicked.connect(self._on_workflow_selected);
        self.ui.add_step_button.clicked.connect(self._add_prompt_step);
        self.ui.remove_step_button.clicked.connect(self._remove_selected_step);
        self.ui.move_step_up_button.clicked.connect(self._move_step_up);
        self.ui.move_step_down_button.clicked.connect(self._move_step_down);
        self.ui.run_workflow_button.clicked.connect(self._start_workflow_execution);
        # Menu Actions
        self.ui.exit_action.triggered.connect(self.close);
        # Assuming ui.py has created help_menu and guide_action/full_guide_action
        if hasattr(self.ui, 'guide_action'):
            self.ui.guide_action.triggered.connect(self._show_templating_guide_dialog) # Renamed slot
        else:
            print("Warning: Could not find 'Templating Guide' menu action to connect.")

        if hasattr(self.ui, 'full_guide_action'):
            self.ui.full_guide_action.triggered.connect(self._show_full_guide_dialog)
        else:
            print("Warning: Could not find 'Application Guide' menu action to connect.")

        print("--- _connect_signals finished ---")

    # --- Slot Methods ---
    # (Referencing self.ui for widgets)

    def _on_prompt_text_changed(self):
        self.variable_update_timer.start() # Debounce
    def _perform_variable_update(self): # Clear & Rebuild variable inputs
        try:
            prompt_text = self.ui.prompt_editor.toPlainText();
            found_variables = sorted(list(set(VARIABLE_PATTERN.findall(prompt_text))));
            while self.ui.variables_form_layout.rowCount() > 0:
                self.ui.variables_form_layout.removeRow(0)
            self.variable_inputs.clear();
            if found_variables:
                for var_name in found_variables:
                    line_edit = QLineEdit();
                    line_edit.setPlaceholderText(f"Value for {{{var_name}}}...");
                    line_edit.setObjectName(f"var_input_{var_name}");
                    label = QLabel(f"{var_name}:");
                    self.variable_inputs[var_name] = line_edit;
                    self.ui.variables_form_layout.addRow(label, line_edit)
            self.ui.variables_groupbox.setVisible(bool(found_variables))
        except Exception as e:
            print(f"CRITICAL ERROR variable UI update: {e}\n{traceback.format_exc()}")

    def _fetch_and_update_models(self):
        print("--- _fetch_and_update_models ---");
        models_url = urllib.parse.urljoin(LM_STUDIO_API_BASE_URL + '/', "models");
        print(f"Fetching models: {models_url}");
        self.statusBar().showMessage("Fetching models...", 0);
        self.ui.refresh_models_button.setEnabled(False)
        try:
            response = requests.get(models_url, timeout=15);
            response.raise_for_status();
            response_data = response.json();
            if "data" not in response_data or not isinstance(response_data["data"], list):
                raise ValueError("Unexpected format")
            model_ids = sorted([model.get("id") for model in response_data["data"] if model.get("id")]);
            print(f"Found models: {model_ids}");
            current_selection = self.ui.model_selection_combo.currentText();
            current_index_if_exists = -1;
            if current_selection != DEFAULT_MODEL_FALLBACK:
                current_index_if_exists = self.ui.model_selection_combo.findText(current_selection)
            self.ui.model_selection_combo.blockSignals(True);
            try:
                self.ui.model_selection_combo.clear();
                if model_ids:
                    self.ui.model_selection_combo.addItems(model_ids);
                    new_index = self.ui.model_selection_combo.findText(current_selection);
                    if new_index != -1:
                        self.ui.model_selection_combo.setCurrentIndex(new_index)
                    elif current_index_if_exists != -1 and current_index_if_exists < self.ui.model_selection_combo.count():
                        self.ui.model_selection_combo.setCurrentIndex(current_index_if_exists)
                    elif self.ui.model_selection_combo.count() > 0:
                        self.ui.model_selection_combo.setCurrentIndex(0)
                    else:
                        self.ui.model_selection_combo.addItem(DEFAULT_MODEL_FALLBACK)
                else:
                    self.ui.model_selection_combo.addItem(DEFAULT_MODEL_FALLBACK)
            finally:
                self.ui.model_selection_combo.blockSignals(False)
            status_msg = f"Models updated ({len(model_ids)} found)." if model_ids else "Models updated. None loaded.";
            self.statusBar().showMessage(status_msg, 3000 if model_ids else 4000)
        except Exception as e:
            error_message = f"Fetch models error: {e.__class__.__name__}";
            print(f"{error_message}: {e}");
            QMessageBox.warning(self, "API Error", f"{error_message}\nCheck LM Studio.");
            self.statusBar().showMessage("Error fetch models.", 5000);
        finally:
            if self.ui.model_selection_combo.count() == 0:
                self.ui.model_selection_combo.blockSignals(True);
                self.ui.model_selection_combo.addItem(DEFAULT_MODEL_FALLBACK);
                self.ui.model_selection_combo.blockSignals(False)
            self.ui.refresh_models_button.setEnabled(True)
        print("--- _fetch_and_update_models finished ---")

    def _handle_chunk_received(self, chunk: str):
        self.ui.generated_output.moveCursor(QTextCursor.MoveOperation.End);
        self.ui.generated_output.insertPlainText(chunk)

    def _generate_prompt(self): # Single prompt generation
        print("--- _generate_prompt ---");
        original_prompt_text = self.ui.prompt_editor.toPlainText();
        if not original_prompt_text.strip():
            QMessageBox.warning(self, "Input Needed", "Prompt empty.");
            return
        final_prompt_text = original_prompt_text;
        missing_values = [];
        currently_displayed_vars = VARIABLE_PATTERN.findall(original_prompt_text)
        for var_name in set(currently_displayed_vars):
            if var_name in self.variable_inputs:
                value = self.variable_inputs[var_name].text().strip();
                if not value:
                    missing_values.append(var_name)
                else:
                    final_prompt_text = final_prompt_text.replace("{" + var_name + "}", value)
            else:
                print(f"Warning: Var '{var_name}' missing input.");
                missing_values.append(f"{var_name} (UI error?)")
        if missing_values:
            QMessageBox.warning(self, "Missing Values", f"Provide values for:\n- {chr(10).join(missing_values)}");
            return
        instruction_suffix = "\n\nIMPORTANT: Respond *only* with the generated text itself.";
        prompt_to_send = final_prompt_text.strip() + instruction_suffix
        selected_model = self.ui.model_selection_combo.currentText();
        if not selected_model or selected_model == DEFAULT_MODEL_FALLBACK:
            QMessageBox.warning(self, "Model Needed", "No valid model selected.");
            return
        if (self.worker_thread and self.worker_thread.isRunning()) or (self.workflow_runner and self.workflow_runner.isRunning()):
            QMessageBox.information(self, "Busy", "Generation/Workflow running.");
            return
        temperature = self.ui.temperature_spinbox.value();
        max_tokens = self.ui.max_tokens_spinbox.value()
        self.ui.generated_output.clear();
        self.ui.generated_output.setPlaceholderText("Generating stream...")
        # Hide workflow log if generating single prompt
        self.workflow_log_dock.setVisible(False)
        if self.progress_dialog is None:
            self.progress_dialog = QProgressDialog("Starting...", "Cancel", 0, 0, self);
            self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal);
            self.progress_dialog.canceled.connect(self._cancel_generation)
        else:
            self.progress_dialog.setLabelText("Starting...");
            self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        self.statusBar().showMessage(f"Generating ({selected_model}, T={temperature}, MT={max_tokens})...", 0);
        self.ui.generate_button.setEnabled(False);
        self.ui.run_workflow_button.setEnabled(False);
        QApplication.processEvents()
        # Create and run the WorkerThread (for single prompts)
        self.worker_thread = WorkerThread(prompt_to_send, LM_STUDIO_API_BASE_URL, selected_model, temperature, max_tokens)
        self.worker_thread.chunk_received.connect(self._handle_chunk_received);
        self.worker_thread.finished.connect(self._handle_generation_result)
        self.worker_thread.start();
        print(f"--- _generate_prompt finished (thread started) ---")

    def _handle_generation_result(self, final_message: str, success: bool):
        """Handles completion of single prompt generation."""
        print(f"--- _handle_generation_result --- Status: {success}, Msg: '{final_message}'");
        if self.progress_dialog:
            self.progress_dialog.hide();
        self.ui.generate_button.setEnabled(True);
        self.ui.run_workflow_button.setEnabled(bool(self.current_workflow_steps)); # Re-enable
        if success:
            status_msg = "Generation complete!";
            print("Stream finished successfully.")
        else:
            status_msg = "Generation failed or cancelled.";
            error_msg_display = f"Error/Cancelled:\n{final_message}";
            if not self.ui.generated_output.toPlainText().strip() and not success :
                self.ui.generated_output.setPlainText(error_msg_display)
            else:
                print(f"Generation final status: {final_message}")
        if not success and "cancelled by user" not in final_message.lower():
            QMessageBox.warning(self, "Generation Problem", final_message)
        self.statusBar().showMessage(status_msg, 3000 if success else 5000);
        self.ui.generated_output.setPlaceholderText("Generated text will appear here...");
        self.ui.generated_output.moveCursor(QTextCursor.MoveOperation.End);
        self.worker_thread = None;
        print("--- _handle_generation_result finished ---")

    def _cancel_generation(self):
        """Requests cancellation of the running generation OR workflow thread."""
        print("--- _cancel_generation ---");
        cancelled_something = False
        if self.worker_thread and self.worker_thread.isRunning():
            print("Requesting cancel generation worker.");
            self.worker_thread.cancel();
            cancelled_something = True
        if self.workflow_runner and self.workflow_runner.isRunning():
            print("Requesting cancel workflow runner.");
            self.workflow_runner.cancel();
            cancelled_something = True

        if not cancelled_something:
            print("Cancel requested, but nothing running.");
        else:
            self.statusBar().showMessage("Attempting to cancel...", 3000)
            # The respective finished/complete signals will handle UI unlock

        # Hide progress immediately on cancel click
        if self.progress_dialog:
            self.progress_dialog.hide();
        self.ui.generate_button.setEnabled(True);
        self.ui.run_workflow_button.setEnabled(bool(self.current_workflow_steps)) # Ensure buttons unlocked
        print("--- _cancel_generation finished ---")

    def _copy_output_to_editor(self):
        print("--- _copy_output_to_editor ---");
        output_text = self.ui.generated_output.toPlainText().strip()
        if not output_text or output_text == self.ui.generated_output.placeholderText() or output_text.startswith("Generating..."):
            QMessageBox.information(self, "Nothing to Copy", "No valid output.");
            self.statusBar().showMessage("Copy failed.", 2000);
            return
        current_editor_text = self.ui.prompt_editor.toPlainText().strip();
        separator = "\n\n---\n\n" if current_editor_text else ""
        self.ui.prompt_editor.setPlainText(current_editor_text + separator + output_text);
        self.ui.prompt_editor.moveCursor(QTextCursor.MoveOperation.End);
        self.statusBar().showMessage("Output appended.", 3000);
        print("--- _copy_output_to_editor finished ---")

    def _apply_stylesheet(self, filepath: str):
        print(f"Applying stylesheet: {filepath}");
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    stylesheet = f.read();
                self.setStyleSheet(stylesheet);
                print("Stylesheet applied.");
            except Exception as e:
                print(f"Error loading stylesheet: {e}");
        else:
            print(f"Stylesheet not found: {filepath}");

    def _populate_category_filter(self):
        print("--- _populate_category_filter ---");
        self.ui.category_filter_combo.blockSignals(True);
        try:
            current_category_data = self.ui.category_filter_combo.currentData();
            self.ui.category_filter_combo.clear();
            self.ui.category_filter_combo.addItem("All Categories", userData=None);
            unique_categories = sorted([cat for cat in self.db_manager.get_unique_categories() if cat is not None]) + [None];
            for category in unique_categories:
                self.ui.category_filter_combo.addItem(category if category is not None else "[Uncategorized]", userData=category)
            index_to_restore = self.ui.category_filter_combo.findData(current_category_data);
            self.ui.category_filter_combo.setCurrentIndex(index_to_restore if index_to_restore != -1 else 0)
        finally:
            self.ui.category_filter_combo.blockSignals(False);
            print("--- _populate_category_filter finished ---")

    def _filter_prompts_by_category(self, index: int):
        if index == -1:
            return;
        print("--- _filter_prompts_by_category ---");
        selected_category = self.ui.category_filter_combo.itemData(index);
        current_search_text = self.ui.search_input.text().strip();
        self._load_prompts_list(category_filter=selected_category, search_query=current_search_text);
        print("--- _filter_prompts_by_category finished ---")

    def _filter_prompts_by_search(self, search_text: str):
        print("--- _filter_prompts_by_search ---");
        selected_category_index = self.ui.category_filter_combo.currentIndex();
        selected_category = self.ui.category_filter_combo.itemData(selected_category_index) if selected_category_index != -1 else None;
        self._load_prompts_list(category_filter=selected_category, search_query=search_text.strip());
        print("--- _filter_prompts_by_search finished ---")

    def _load_prompts_list(self, category_filter: str | None = None, search_query: str | None = None):
        print(f"--- _load_prompts_list ---");
        self.ui.prompt_list.clear();
        self.ui.prompt_preview.clear();
        prompts_to_filter = self.db_manager.get_prompts_by_category(category_filter) if category_filter is not None else self.db_manager.get_all_prompts()
        if not prompts_to_filter:
            self.statusBar().showMessage("No prompts match category.", 3000);
            return
        search_query_lower = search_query.strip().lower() if search_query else None
        if search_query_lower:
            filtered_prompts = [p for p in prompts_to_filter if (p[1] and search_query_lower in p[1].lower()) or (p[2] and search_query_lower in p[2].lower()) or (p[3] and search_query_lower in p[3].lower())]
        else:
            filtered_prompts = prompts_to_filter
        if not filtered_prompts:
            self.statusBar().showMessage("No prompts match filters.", 3000);
            return
        for prompt_id, prompt_text, category, notes, created_at, _out_var in filtered_prompts:
            display_text = prompt_text.split('\n', 1)[0];
            if len(display_text) > 60:
                display_text = display_text[:60].strip() + "...";
            category_display = category if category is not None else "[Uncategorized]";
            list_entry_text = f"[{category_display}] {display_text}";
            item = QListWidgetItem(list_entry_text);
            item.setData(QtCore.Qt.ItemDataRole.UserRole, prompt_id);
            self.ui.prompt_list.addItem(item)
        self.statusBar().showMessage(f"Loaded {len(filtered_prompts)} prompts.", 3000);
        print(f"--- _load_prompts_list finished ({len(filtered_prompts)}) ---")

    def _display_selected_prompt_preview(self, item: QListWidgetItem | None):
        if not item:
            self.ui.prompt_preview.clear();
            self.ui.prompt_preview.setPlaceholderText("Select prompt for preview.");
            return
        prompt_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if prompt_id is not None:
            prompt_data = self.db_manager.get_prompt_by_id(prompt_id);
            if prompt_data:
                _id, txt, cat, nts, crtd, out_var = prompt_data;
                cat_s = cat if cat else "[Uncat.]";
                nts_s = f"\n\nNotes:\n{nts.strip()}" if nts and ns.strip() else ""; # Fixed typo nts -> ns
                txt_s = f"\n\nPrompt:\n{txt.strip()}";
                ov_s = f"\nOutput Var: {{{out_var}}}" if out_var else "";
                self.ui.prompt_preview.setPlainText(f"Cat: {cat_s}\nCreated: {crtd}{ov_s}{nts_s}{txt_s}")
            else:
                self.ui.prompt_preview.setPlainText(f"Error: Cannot retrieve ID {prompt_id}.");
                self.statusBar().showMessage(f"Error retrieving ID: {prompt_id}", 5000)
        else:
            self.ui.prompt_preview.clear();
            self.ui.prompt_preview.setPlaceholderText("Select prompt for preview.")

    def _load_selected_prompt_to_editor(self):
        print("--- _load_selected_prompt_to_editor ---");
        selected_items = self.ui.prompt_list.selectedItems();
        if not selected_items:
            QMessageBox.information(self, "Nothing Selected", "Select prompt to load.");
            self.statusBar().showMessage("Load failed.", 3000);
            return
        selected_item = selected_items[0];
        prompt_id = selected_item.data(QtCore.Qt.ItemDataRole.UserRole)
        if prompt_id is None:
            self.statusBar().showMessage("Error: Missing ID.", 5000);
            self.current_prompt_id = None;
            self.setWindowTitle("NovaPrompt Lab");
            return
        prompt_data = self.db_manager.get_prompt_by_id(prompt_id)
        if prompt_data:
            _id, text, cat, notes, _c, out_var = prompt_data;
            self.ui.prompt_editor.blockSignals(True);
            self.ui.prompt_editor.setPlainText(text);
            self.ui.prompt_editor.blockSignals(False);
            self._perform_variable_update();
            self.ui.category_input.setText(cat if cat else "");
            self.ui.notes_input.setPlainText(notes if notes else "");
            self.ui.output_variable_input.setText(out_var if out_var else "");
            self.current_prompt_id = prompt_id;
            self.setWindowTitle(f"Editing: {selected_item.text()}");
            self.statusBar().showMessage(f"Loaded: {selected_item.text()}", 3000);
        else:
            self.statusBar().showMessage(f"Error loading ID: {prompt_id}.", 5000);
            self.current_prompt_id = None;
            self.setWindowTitle("NovaPrompt Lab");
            self._clear_editor()
        print("--- _load_selected_prompt_to_editor finished ---")

    def _delete_selected_prompt(self):
        print("--- _delete_selected_prompt ---");
        selected_items = self.ui.prompt_list.selectedItems();
        if not selected_items:
            QMessageBox.information(self, "Nothing Selected", "Select prompt to delete.");
            self.statusBar().showMessage("Delete failed.", 3000);
            return
        selected_item = selected_items[0];
        prompt_id = selected_item.data(QtCore.Qt.ItemDataRole.UserRole);
        prompt_title = selected_item.text()
        if prompt_id is None:
            self.statusBar().showMessage("Error deleting: Missing ID.", 5000);
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{prompt_title}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.delete_prompt(prompt_id):
                self.statusBar().showMessage(f"Deleted: '{prompt_title}'", 3000);
                if self.current_prompt_id == prompt_id:
                    self._clear_editor()
                self._populate_category_filter();
                self._filter_prompts_by_search(self.ui.search_input.text().strip());
                self.ui.prompt_preview.clear()
            else:
                QMessageBox.warning(self, "Deletion Failed", f"Could not delete.");
                self.statusBar().showMessage(f"Failed delete: '{prompt_title}'", 5000)
        else:
            self.statusBar().showMessage("Deletion cancelled.", 2000)
        print("--- _delete_selected_prompt finished ---")

    def _clear_editor(self):
        print("--- _clear_editor ---");
        self.ui.prompt_editor.blockSignals(True);
        self.ui.prompt_editor.clear();
        self.ui.prompt_editor.blockSignals(False);
        self._perform_variable_update();
        self.ui.category_input.clear();
        self.ui.notes_input.clear();
        self.ui.output_variable_input.clear();
        self.ui.generated_output.clear();
        self.ui.generated_output.setPlaceholderText("Generated text will appear here...");
        self.current_prompt_id = None;
        self.setWindowTitle("NovaPrompt Lab");
        self.ui.prompt_list.clearSelection();
        self.ui.prompt_preview.clear();
        self.statusBar().showMessage("Editor cleared.", 2000);
        print("--- _clear_editor finished ---")

    def _save_current_prompt(self):
        print("--- _save_current_prompt ---");
        prompt_text = self.ui.prompt_editor.toPlainText()
        if not prompt_text.strip():
            QMessageBox.warning(self, "Cannot Save", "Prompt empty.");
            return
        category = self.ui.category_input.text().strip() or None;
        notes = self.ui.notes_input.toPlainText().strip() or None;
        output_variable_name = self.ui.output_variable_input.text().strip() or None
        if output_variable_name and not re.fullmatch(r"[a-zA-Z0-9_]+", output_variable_name):
            QMessageBox.warning(self, "Invalid Name", "Output Var Name invalid.");
            return
        status_message = "";
        message_timeout = 3000;
        saved_prompt_id = None
        try:
            if self.current_prompt_id is None:
                new_id = self.db_manager.add_prompt(prompt_text, category, notes, output_variable_name);
                if new_id is not None:
                    saved_prompt_id = new_id;
                    self.current_prompt_id = new_id;
                    status_message = f"Prompt added (ID: {new_id})";
                    self.setWindowTitle(f"Editing ID: {self.current_prompt_id}");
                    print(f"Added ID: {new_id}")
                else:
                    status_message = "Failed add.";
                    message_timeout = 5000;
                    QMessageBox.critical(self, "Save Failed", "Could not add.")
            else: # Update existing
                if self.db_manager.update_prompt(self.current_prompt_id, prompt_text, category, notes, output_variable_name):
                    saved_prompt_id = self.current_prompt_id;
                    status_message = f"Prompt updated (ID: {self.current_prompt_id})";
                    print(f"Updated ID: {self.current_prompt_id}")
                else:
                    status_message = f"Failed update (ID: {self.current_prompt_id}).";
                    message_timeout = 5000;
                    QMessageBox.critical(self, "Update Failed", f"Could not update ID {self.current_prompt_id}.")
            if saved_prompt_id is not None:
                self._populate_category_filter();
                self._filter_prompts_by_search(self.ui.search_input.text().strip());
                item_to_select = None;
                for i in range(self.ui.prompt_list.count()):
                    item = self.ui.prompt_list.item(i);
                    if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == saved_prompt_id:
                        item_to_select = item;
                        break
                if item_to_select:
                    self.ui.prompt_list.setCurrentItem(item_to_select);
                    self._display_selected_prompt_preview(item_to_select);
                    self.setWindowTitle(f"Editing: {item_to_select.text()}")
                else:
                    self.setWindowTitle(f"Editing ID: {saved_prompt_id}") # Fallback
            self.statusBar().showMessage(status_message, message_timeout)
        except Exception as e:
            print(f"Error save: {e}");
            QMessageBox.critical(self, "Save Error", f"Error:\n{e}");
            self.statusBar().showMessage("Save failed.", 5000)
        print("--- _save_current_prompt finished ---")

    def closeEvent(self, event):
        print("--- closeEvent ---");
        worker_running = False;
        wf_runner_running = False;
        if self.worker_thread and self.worker_thread.isRunning():
            worker_running = True;
            print("Closing: Worker running. Cancelling...");
            self.worker_thread.cancel();
        if self.workflow_runner and self.workflow_runner.isRunning():
            wf_runner_running = True;
            print("Closing: Workflow running. Cancelling...");
            self.workflow_runner.cancel();
        # Wait for threads to finish (with a timeout)
        if worker_running and not self.worker_thread.wait(2000):
            print("Closing: Worker didn't finish quickly.")
        if wf_runner_running and not self.workflow_runner.wait(2000):
            print("Closing: Workflow runner didn't finish quickly.")
        print("Closing: Closing database...");
        self.db_manager.close_connection();
        event.accept();
        print("--- closeEvent finished ---")

    def _show_templating_guide_dialog(self): # Renamed for clarity
        self._show_guide_dialog("Prompt Templating Guide", "guide.html")
    def _show_full_guide_dialog(self): # New method for full guide
        self._show_guide_dialog("NovaPrompt Lab - Full Guide", "full_guide.html")
    def _show_guide_dialog(self, title: str, guide_filename: str):
        """Displays a scrollable message box with content from an HTML file."""
        guide_text = f"Could not load {guide_filename}";
        if os.path.exists(guide_filename):
            try:
                with open(guide_filename, "r", encoding="utf-8") as f:
                    guide_text = f.read()
            except Exception as e:
                print(f"Error reading {guide_filename}: {e}")
        else:
            print(f"Guide file not found: {guide_filename}")

        msg_box = QMessageBox(self);
        msg_box.setWindowTitle(title);
        msg_box.setIcon(QMessageBox.Icon.Information);
        scroll = QScrollArea(msg_box);
        scroll.setWidgetResizable(True);
        content = QTextEdit();
        content.setHtml(guide_text);
        content.setReadOnly(True);
        scroll.setWidget(content);
        scroll.setMinimumSize(QSize(650, 500));
        grid_layout = msg_box.layout();
        grid_layout.addWidget(scroll, 1, 0, 1, grid_layout.columnCount(), Qt.AlignmentFlag.AlignCenter);
        msg_box.addButton(QMessageBox.StandardButton.Ok);
        msg_box.exec()


    # --- Workflow Management Slots ---
    def _load_workflows_list(self):
        print("--- _load_workflows_list ---");
        self.ui.workflow_list.clear();
        self.workflows_data = self.db_manager.get_all_workflows();
        if not self.workflows_data:
            self.ui.workflow_list.addItem("No workflows defined.");
            self.ui.workflow_list.setEnabled(False);
            self.ui.delete_workflow_button.setEnabled(False);
            return
        self.ui.workflow_list.setEnabled(True);
        self.ui.delete_workflow_button.setEnabled(True)
        for wf_id, name, description in self.workflows_data:
            item = QListWidgetItem(name);
            item.setData(Qt.ItemDataRole.UserRole, wf_id);
            item.setToolTip(description or "No description");
            self.ui.workflow_list.addItem(item)
        if self.ui.workflow_list.count() > 0:
            self.ui.workflow_list.setCurrentRow(0);
            self._on_workflow_selected(self.ui.workflow_list.item(0))

    def _on_workflow_selected(self, item: QListWidgetItem | None):
        self.ui.workflow_steps_list.clear();
        self.current_workflow_id = None;
        self.current_workflow_steps = [];
        self.ui.run_workflow_button.setEnabled(False);
        if not item:
            print("Workflow deselected.");
            return
        self.current_workflow_id = item.data(Qt.ItemDataRole.UserRole);
        print(f"Workflow selected: ID={self.current_workflow_id}, Name={item.text()}")
        if self.current_workflow_id is not None:
            self._load_workflow_steps(self.current_workflow_id);
            self.ui.run_workflow_button.setEnabled(bool(self.current_workflow_steps))

    def _load_workflow_steps(self, workflow_id: int):
        print(f"--- _load_workflow_steps ID: {workflow_id} ---");
        self.ui.workflow_steps_list.clear()
        steps_ids = self.db_manager.get_workflow_steps(workflow_id)
        if steps_ids is None:
            QMessageBox.warning(self, "Error", f"Could not load steps.");
            self.current_workflow_steps = [];
            self.ui.run_workflow_button.setEnabled(False);
        elif not steps_ids:
            self.ui.workflow_steps_list.addItem("No steps added yet.");
            self.ui.workflow_steps_list.setEnabled(False);
            self.current_workflow_steps = [];
            self.ui.run_workflow_button.setEnabled(False);
        else:
            self.current_workflow_steps = steps_ids;
            self.ui.workflow_steps_list.setEnabled(True);
            print(f"  Steps found: {self.current_workflow_steps}");
            self.ui.run_workflow_button.setEnabled(True);
            for step_index, prompt_id in enumerate(self.current_workflow_steps):
                prompt_data = self.db_manager.get_prompt_by_id(prompt_id)
                if prompt_data:
                    _id, text, _c, _n, _cr, out_var = prompt_data;
                    display_text = text.split('\n', 1)[0];
                    if len(display_text) > 50:
                        display_text = display_text[:50].strip() + "...";
                    output_indicator = f" -> {{{out_var}}}" if out_var else "";
                    item_text = f"{step_index + 1}. {display_text}{output_indicator}";
                    item = QListWidgetItem(item_text);
                    item.setData(Qt.ItemDataRole.UserRole, prompt_id);
                    item.setToolTip(f"ID: {prompt_id} OutVar: {out_var or 'N/A'}\n---\n{text}");
                    self.ui.workflow_steps_list.addItem(item)
                else:
                    item = QListWidgetItem(f"{step_index + 1}. [Error: Prompt ID {prompt_id} missing!]");
                    item.setData(Qt.ItemDataRole.UserRole, prompt_id);
                    self.ui.workflow_steps_list.addItem(item);
                    print(f"Warning: Prompt ID {prompt_id} missing.")
            if self.ui.workflow_steps_list.count() > 0:
                self.ui.workflow_steps_list.setCurrentRow(0)

    def _add_new_workflow(self):
        print("--- _add_new_workflow ---");
        name, ok = QInputDialog.getText(self, "New Workflow", "Workflow name:")
        if ok and name and name.strip():
            workflow_name = name.strip();
            new_id = self.db_manager.add_workflow(workflow_name)
            if new_id is not None:
                self._load_workflows_list();
                item_to_select = None;
                for i in range(self.ui.workflow_list.count()):
                    item = self.ui.workflow_list.item(i);
                    if item and item.data(Qt.ItemDataRole.UserRole) == new_id:
                        item_to_select = item;
                        break;
                if item_to_select:
                    self.ui.workflow_list.setCurrentItem(item_to_select);
                    self._on_workflow_selected(item_to_select)
                self.statusBar().showMessage(f"Workflow '{workflow_name}' created.", 3000)
            else:
                QMessageBox.warning(self, "Error", f"Could not create '{workflow_name}'. Name exists?")
        elif ok:
            QMessageBox.warning(self, "Input Needed", "Name cannot be empty.")

    def _delete_selected_workflow(self):
        print("--- _delete_selected_workflow ---");
        selected_items = self.ui.workflow_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Nothing Selected", "Select workflow to delete.");
            return
        selected_item = selected_items[0];
        workflow_id = selected_item.data(Qt.ItemDataRole.UserRole);
        workflow_name = selected_item.text()
        if workflow_id is None:
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete workflow '{workflow_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.delete_workflow(workflow_id):
                self.statusBar().showMessage(f"Workflow '{workflow_name}' deleted.", 3000);
                if self.current_workflow_id == workflow_id:
                    self.ui.workflow_steps_list.clear();
                    self.current_workflow_id = None;
                    self.current_workflow_steps = [];
                    self.ui.run_workflow_button.setEnabled(False)
                self._load_workflows_list()
            else:
                QMessageBox.warning(self, "Error", f"Could not delete workflow.");
                self.statusBar().showMessage("Workflow delete failed.", 5000)

    def _add_prompt_step(self):
        print("--- _add_prompt_step ---");
        if self.current_workflow_id is None:
            QMessageBox.warning(self, "No Workflow", "Select workflow first.");
            return
        selected_prompt_items = self.ui.prompt_list.selectedItems() # From Prompts Tab
        if not selected_prompt_items:
            QMessageBox.warning(self, "No Prompt", "Select prompt from 'Prompts' tab.");
            return
        prompt_id_to_add = selected_prompt_items[0].data(Qt.ItemDataRole.UserRole)
        if prompt_id_to_add is None:
            QMessageBox.warning(self, "Error", "Selected prompt has no ID.");
            return
        self.current_workflow_steps.append(prompt_id_to_add) # Add ID
        if self.db_manager.update_workflow_steps(self.current_workflow_id, self.current_workflow_steps):
            self.statusBar().showMessage(f"Step added.", 3000);
            self._load_workflow_steps(self.current_workflow_id); # Refresh
        else:
            self.statusBar().showMessage(f"Failed save steps.", 5000);
            self.current_workflow_steps.pop();
            QMessageBox.critical(self, "Error", "Could not save steps.")

    def _remove_selected_step(self):
        print("--- _remove_selected_step ---");
        if self.current_workflow_id is None or not self.current_workflow_steps:
            return
        selected_items = self.ui.workflow_steps_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Nothing Selected", "Select step to remove.");
            return
        current_row = self.ui.workflow_steps_list.row(selected_items[0])
        if 0 <= current_row < len(self.current_workflow_steps):
            removed_id = self.current_workflow_steps.pop(current_row);
            print(f"Removed step index {current_row} (ID: {removed_id})")
            if self.db_manager.update_workflow_steps(self.current_workflow_id, self.current_workflow_steps):
                self.statusBar().showMessage(f"Step removed.", 3000);
                self._load_workflow_steps(self.current_workflow_id);
                new_row = min(current_row, self.ui.workflow_steps_list.count() - 1);
                if new_row >= 0:
                    self.ui.workflow_steps_list.setCurrentRow(new_row)
            else:
                self.statusBar().showMessage(f"Failed save after removal.", 5000);
                self.current_workflow_steps.insert(current_row, removed_id);
                QMessageBox.critical(self, "Error", "Could not save after removal.")

    def _move_step_up(self):
        print("--- _move_step_up ---");
        if self.current_workflow_id is None or len(self.current_workflow_steps) < 2:
            return
        current_row = self.ui.workflow_steps_list.currentRow()
        if current_row > 0:
            self.current_workflow_steps[current_row], self.current_workflow_steps[current_row - 1] = self.current_workflow_steps[current_row - 1], self.current_workflow_steps[current_row]
            if self.db_manager.update_workflow_steps(self.current_workflow_id, self.current_workflow_steps):
                self.statusBar().showMessage(f"Step moved up.", 3000);
                prev_selection = current_row - 1;
                self._load_workflow_steps(self.current_workflow_id);
                self.ui.workflow_steps_list.setCurrentRow(prev_selection)
            else:
                self.statusBar().showMessage(f"Failed save after move.", 5000);
                self.current_workflow_steps[current_row], self.current_workflow_steps[current_row - 1] = self.current_workflow_steps[current_row - 1], self.current_workflow_steps[current_row];
                QMessageBox.critical(self, "Error", "Could not save after move.")
        else:
            self.statusBar().showMessage("Cannot move first step up.", 2000)

    def _move_step_down(self):
        print("--- _move_step_down ---");
        if self.current_workflow_id is None or len(self.current_workflow_steps) < 2:
            return
        current_row = self.ui.workflow_steps_list.currentRow()
        if 0 <= current_row < len(self.current_workflow_steps) - 1:
            self.current_workflow_steps[current_row], self.current_workflow_steps[current_row + 1] = self.current_workflow_steps[current_row + 1], self.current_workflow_steps[current_row]
            if self.db_manager.update_workflow_steps(self.current_workflow_id, self.current_workflow_steps):
                self.statusBar().showMessage(f"Step moved down.", 3000);
                new_selection = current_row + 1;
                self._load_workflow_steps(self.current_workflow_id);
                self.ui.workflow_steps_list.setCurrentRow(new_selection)
            else:
                self.statusBar().showMessage(f"Failed save after move.", 5000);
                self.current_workflow_steps[current_row], self.current_workflow_steps[current_row + 1] = self.current_workflow_steps[current_row + 1], self.current_workflow_steps[current_row];
                QMessageBox.critical(self, "Error", "Could not save after move.")
        else:
            self.statusBar().showMessage("Cannot move last step down.", 2000)

    # --- Workflow Execution Slots ---
    def _start_workflow_execution(self):
        print("--- _start_workflow_execution ---")
        if not self.current_workflow_id or not self.current_workflow_steps:
            QMessageBox.warning(self, "Cannot Run", "No workflow/steps selected.");
            return
        if (self.worker_thread and self.worker_thread.isRunning()) or (self.workflow_runner and self.workflow_runner.isRunning()):
            QMessageBox.information(self, "Busy", "Generation/Workflow running.");
            return

        initial_inputs_needed = self._get_required_initial_inputs(self.current_workflow_steps)
        if initial_inputs_needed is None:
            QMessageBox.critical(self, "Workflow Error", "Cannot analyze steps.");
            return

        initial_variables = {}
        if initial_inputs_needed:
            print(f"Workflow requires initial inputs: {initial_inputs_needed}")
            # Use the custom input dialog
            dialog = WorkflowInputDialog(initial_inputs_needed, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                values = dialog.get_values()
                if values is None:
                    return # Input validation failed
                initial_variables = values;
                print(f"Received initial variables: {initial_variables}")
            else:
                print("Workflow cancelled by user input.");
                self.statusBar().showMessage("Workflow cancelled.", 3000);
                return

        selected_model = self.ui.model_selection_combo.currentText()
        if not selected_model or selected_model == DEFAULT_MODEL_FALLBACK:
            QMessageBox.warning(self, "Model Needed", "No valid model selected.");
            return
        temperature = self.ui.temperature_spinbox.value();
        max_tokens = self.ui.max_tokens_spinbox.value()

        # Clear output areas and show log dock
        self.ui.generated_output.clear();
        self.ui.generated_output.setPlaceholderText("Running workflow...")
        self.workflow_log_output.clear();
        self.workflow_log_dock.setVisible(True)

        self.statusBar().showMessage(f"Running workflow (Model: {selected_model})...", 0)
        self.ui.run_workflow_button.setEnabled(False);
        self.ui.generate_button.setEnabled(False)
        QApplication.processEvents() # Update UI

        # Create and start WorkflowRunner thread
        # Pass a copy of current_workflow_steps to avoid modification during execution
        self.workflow_runner = WorkflowRunner(
            workflow_steps=list(self.current_workflow_steps),
            initial_variables=initial_variables,
            db_manager=self.db_manager,
            api_base_url=LM_STUDIO_API_BASE_URL,
            model_name=selected_model,
            temperature=temperature,
            max_tokens=max_tokens,
            parent=self # Set parent for signal/slot connections
        )
        self.workflow_runner.step_started.connect(self._handle_workflow_step_started);
        self.workflow_runner.step_finished.connect(self._handle_workflow_step_output);
        self.workflow_runner.workflow_complete.connect(self._handle_workflow_finished);
        self.workflow_runner.error_occurred.connect(self._handle_workflow_error);
        self.workflow_runner.start();
        print("WorkflowRunner thread started.")

    def _get_required_initial_inputs(self, step_ids: list[int]) -> list[str] | None:
        print("--- Analyzing workflow inputs ---");
        all_required_vars = set();
        provided_vars = set()
        try:
            for i, prompt_id in enumerate(step_ids):
                prompt_data = self.db_manager.get_prompt_by_id(prompt_id)
                if not prompt_data:
                    print(f"Error: Cannot find ID {prompt_id}.");
                    return None
                _id, tmplt, _cat, _nts, _c, out_var = prompt_data;
                step_required = set(VARIABLE_PATTERN.findall(tmplt));
                print(f"  Step {i+1} (ID {prompt_id}): Req={step_required or '{}'}, Out='{out_var}'");
                all_required_vars.update(step_required);
                if out_var:
                    provided_vars.add(out_var)
            initial_needed = sorted(list(all_required_vars - provided_vars));
            print(f"  Initial inputs needed: {initial_needed}");
            return initial_needed
        except Exception as e:
            print(f"Error analyzing workflow: {e}");
            return None

    def _handle_workflow_step_started(self, step_index: int, description: str):
        log_msg = f"--- Starting Step {step_index + 1}/{len(self.current_workflow_steps)} ---\n{description}\n"
        print(log_msg.strip());
        self.workflow_log_output.append(log_msg);
        self.statusBar().showMessage(f"Running Step {step_index + 1}/{len(self.current_workflow_steps)}: {description}", 0)

    def _handle_workflow_step_output(self, step_index: int, output_var_name: str, output_text: str):
        # Log intermediate output to the workflow log dock
        print(f"WF Step {step_index + 1} Finished. Output Var: {{{output_var_name}}}")
        print(f"  Output Text Snippet: {output_text[:80]}...") # Print snippet to console log

        log_msg = f"--- Step {step_index + 1} Finished ---\n";
        if output_var_name != "[No Output Var]":
            log_msg += f"Output Variable: {{{output_var_name}}}\n"
        log_msg += f"Output Text:\n{output_text}\n"; # Include the full output in the log
        self.workflow_log_output.append(log_msg)


    def _handle_workflow_finished(self, final_output: str, success: bool):
        """Handles workflow completion signal."""
        print(f"--- _handle_workflow_finished --- Success: {success}");

        # Re-enable run/generate buttons
        self.ui.run_workflow_button.setEnabled(bool(self.current_workflow_steps));
        self.ui.generate_button.setEnabled(True)

        log_msg = f"--- Workflow {'Completed Successfully' if success else 'Failed/Cancelled'} ---\n"

        if success:
            status_msg = "Workflow completed successfully!";
            self.ui.generated_output.setPlainText(final_output); # Show final output in main output area
            log_msg += "Final output displayed in the main output area."
        else:
            status_msg = "Workflow failed or cancelled.";
            self.ui.generated_output.setPlainText(f"Workflow Failed:\n{final_output}"); # Show error in main output area
            log_msg += f"Failure Reason: {final_output}"

        self.workflow_log_output.append(log_msg); # Log final status

        self.statusBar().showMessage(status_msg, 4000 if success else 5000);
        self.ui.generated_output.setPlaceholderText("Generated text will appear here..."); # Restore placeholder if output area was cleared manually
        self.ui.generated_output.moveCursor(QTextCursor.MoveOperation.End); # Ensure cursor is at end

        self.workflow_runner = None; # Clear runner reference
        print("--- _handle_workflow_finished finished ---")


    def _handle_workflow_error(self, error_message: str):
        """Handles errors emitted specifically by the WorkflowRunner."""
        print(f"--- _handle_workflow_error ---: {error_message}");
        log_msg = f"--- WORKFLOW ERROR ---\n{error_message}\n";
        self.workflow_log_output.append(log_msg); # Log error to the workflow log dock
        # Display a critical message box immediately for high visibility
        QMessageBox.critical(self, "Workflow Execution Error", error_message);
        # The finished signal will be emitted after this, which handles UI state cleanup.


# --- Main application entry point ---
def main():
    """Main function to start the NovaPrompt Lab application."""
    print("--- main function started ---")
    # Enable High DPI scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv);
    app.setOrganizationName("NovaPrompt");
    app.setApplicationName("NovaPromptLab")

    main_window = MainWindow();
    main_window.show()

    # Start the Qt event loop
    exit_code = app.exec();
    print(f"--- Application exiting with code: {exit_code} ---");
    sys.exit(exit_code)

# --- Script Execution Guard ---
if __name__ == "__main__":
    main()