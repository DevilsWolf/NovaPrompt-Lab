# ui.py - UI Setup Class for NovaPrompt Lab (Verified)

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QListWidget, QSplitter,
                             QLabel, QLineEdit, QComboBox, QFormLayout,
                             QDoubleSpinBox, QSpinBox, QGroupBox, QScrollArea,
                             QTabWidget, QAbstractItemView)
from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QAction, QKeySequence

# Constants - Default values for UI elements if not set otherwise
DEFAULT_MODEL_FALLBACK = "No models loaded/found"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024

class Ui_MainWindow:
    """Handles the creation and layout of UI widgets for the main window."""

    def setup_ui(self, main_window: QMainWindow):
        """Creates and arranges all UI elements within the main window."""
        print("--- UI setup started ---")
        main_window.setObjectName("MainWindow") # Name for potential top-level styling

        central_widget = QWidget(main_window)
        main_window.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar - Actions defined here, connections made in MainWindow
        self._create_menu_bar(main_window)

        # Main horizontal splitter (Left Panel | Right Area)
        self.main_splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Create and add panels to the splitter
        left_panel_widget = self._create_left_panel_with_tabs(self.main_splitter)
        self.main_splitter.addWidget(left_panel_widget)
        right_area = self._create_right_area(self.main_splitter)
        self.main_splitter.addWidget(right_area)

        # Store reference to main window if needed (e.g., for status bar access)
        self.main_window_ref = main_window
        self.main_window_ref.statusBar().showMessage("Ready") # Set initial status

        print("--- UI setup finished ---")

    # --- Menu Creation ---
    def _create_menu_bar(self, parent_window: QMainWindow):
        """Creates the main menu bar (File, Help)."""
        self.menu_bar = parent_window.menuBar()
        # File Menu
        self.file_menu = self.menu_bar.addMenu("&File")
        self.exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", parent_window)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.setStatusTip("Exit the application")
        # exit_action.triggered.connect(parent_window.close) # Connected in MainWindow
        self.file_menu.addAction(self.exit_action)

        # Help Menu
        self.help_menu = self.menu_bar.addMenu("&Help")
        self.guide_action = QAction("Prompt Templating &Guide", parent_window)
        self.guide_action.setStatusTip("Show guide on how to use prompt templates with {variables}")
        self.guide_action.setShortcut(QKeySequence.StandardKey.HelpContents) # F1
        # guide_action.triggered.connect(...) # Connected in MainWindow
        self.help_menu.addAction(self.guide_action)
        # Add separator before potential About action
        self.help_menu.addSeparator()
        # self.about_action = QAction("&About...", parent_window)
        # self.help_menu.addAction(self.about_action)

    # --- Panel/Section Creation Methods ---

    def _create_left_panel_with_tabs(self, parent_widget: QWidget) -> QWidget:
        """Creates the main left panel containing tabs for Prompts and Workflows."""
        left_panel = QWidget(parent_widget)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0); left_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("LeftTabWidget")

        # Create content widgets for each tab
        prompts_tab_widget = self._create_prompts_tab(self.tab_widget)
        workflows_tab_widget = self._create_workflows_tab(self.tab_widget)

        # Add tabs
        self.tab_widget.addTab(prompts_tab_widget, "Prompts")
        self.tab_widget.addTab(workflows_tab_widget, "Workflows")

        left_layout.addWidget(self.tab_widget)
        return left_panel

    def _create_prompts_tab(self, parent_widget: QWidget) -> QWidget:
        """Creates the content widget for the 'Prompts' tab."""
        prompts_tab = QWidget(parent_widget)
        left_layout = QVBoxLayout(prompts_tab)
        left_layout.setContentsMargins(5, 5, 5, 5); left_layout.setSpacing(8)

        # Filter/Search
        filter_search_layout = QVBoxLayout(); filter_search_layout.setSpacing(10)
        category_filter_layout = QHBoxLayout(); category_filter_label = QLabel("Filter by Category:")
        self.category_filter_combo = QComboBox(); category_filter_layout.addWidget(category_filter_label); category_filter_layout.addWidget(self.category_filter_combo, 1); filter_search_layout.addLayout(category_filter_layout)
        search_layout = QHBoxLayout(); search_label = QLabel("Search Prompts:")
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Enter keywords..."); search_layout.addWidget(search_label); search_layout.addWidget(self.search_input, 1); filter_search_layout.addLayout(search_layout)
        left_layout.addLayout(filter_search_layout)

        # Prompt List
        list_label = QLabel("Saved Prompts:")
        self.prompt_list = QListWidget(); self.prompt_list.setObjectName("PromptListWidget"); self.prompt_list.setSortingEnabled(False); left_layout.addWidget(list_label); left_layout.addWidget(self.prompt_list, 1)

        # Preview Area
        preview_label = QLabel("Preview:")
        self.prompt_preview = QTextEdit(); self.prompt_preview.setObjectName("PromptPreview"); self.prompt_preview.setReadOnly(True); self.prompt_preview.setPlaceholderText("Select a prompt..."); self.prompt_preview.setMaximumHeight(250); left_layout.addWidget(preview_label); left_layout.addWidget(self.prompt_preview)

        # Prompt List Buttons
        list_buttons_layout = QHBoxLayout(); self.load_button = QPushButton("Load Selected"); self.delete_button = QPushButton("Delete Selected"); list_buttons_layout.addWidget(self.load_button); list_buttons_layout.addWidget(self.delete_button); left_layout.addLayout(list_buttons_layout)
        return prompts_tab

    def _create_workflows_tab(self, parent_widget: QWidget) -> QWidget:
        """Creates the content widget for the 'Workflows' tab."""
        workflows_tab = QWidget(parent_widget)
        layout = QHBoxLayout(workflows_tab); layout.setContentsMargins(5, 5, 5, 5); layout.setSpacing(8)

        # Workflow List Area (Left side of tab)
        workflow_list_area = QWidget(); workflow_list_layout = QVBoxLayout(workflow_list_area); workflow_list_layout.setSpacing(5)
        workflow_list_label = QLabel("Workflows:"); self.workflow_list = QListWidget(); self.workflow_list.setObjectName("WorkflowListWidget")
        wf_list_buttons_layout = QHBoxLayout(); self.new_workflow_button = QPushButton("New"); self.delete_workflow_button = QPushButton("Delete"); wf_list_buttons_layout.addWidget(self.new_workflow_button); wf_list_buttons_layout.addWidget(self.delete_workflow_button); wf_list_buttons_layout.addStretch()
        workflow_list_layout.addWidget(workflow_list_label); workflow_list_layout.addWidget(self.workflow_list, 1); workflow_list_layout.addLayout(wf_list_buttons_layout)

        # Steps Area (Right side of tab)
        steps_area = QWidget(); steps_layout = QVBoxLayout(steps_area); steps_layout.setSpacing(5)
        steps_list_label = QLabel("Workflow Steps (Sequence):"); self.workflow_steps_list = QListWidget(); self.workflow_steps_list.setObjectName("WorkflowStepsList"); self.workflow_steps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection) # Select one step at a time
        step_buttons_layout = QHBoxLayout(); self.add_step_button = QPushButton("Add Prompt as Step"); self.remove_step_button = QPushButton("Remove Step"); self.move_step_up_button = QPushButton("Up"); self.move_step_down_button = QPushButton("Down")
        step_buttons_layout.addWidget(self.add_step_button); step_buttons_layout.addWidget(self.remove_step_button); step_buttons_layout.addStretch(); step_buttons_layout.addWidget(self.move_step_up_button); step_buttons_layout.addWidget(self.move_step_down_button)
        steps_layout.addWidget(steps_list_label); steps_layout.addWidget(self.workflow_steps_list, 1); steps_layout.addLayout(step_buttons_layout)

        # Workflow Execution Area
        run_layout = QHBoxLayout(); self.run_workflow_button = QPushButton("Run Workflow"); self.run_workflow_button.setObjectName("RunWorkflowButton"); self.run_workflow_button.setEnabled(False); # Disabled until workflow selected
        run_layout.addStretch(); run_layout.addWidget(self.run_workflow_button); steps_layout.addLayout(run_layout)

        # Add workflow list and steps area to the tab layout
        layout.addWidget(workflow_list_area, 1) # Stretch factor 1
        layout.addWidget(steps_area, 2) # Stretch factor 2 (more space for steps)
        return workflows_tab

    def _create_right_area(self, parent_widget: QWidget) -> QWidget:
        """Creates the right area widget containing the editor/output splitter."""
        right_area = QWidget(parent_widget)
        right_layout = QVBoxLayout(right_area); right_layout.setContentsMargins(5, 5, 5, 5)
        self.right_splitter = QSplitter(QtCore.Qt.Orientation.Vertical); right_layout.addWidget(self.right_splitter)
        editor_section_widget = self._create_editor_section(self.right_splitter); self.right_splitter.addWidget(editor_section_widget)
        output_section_widget = self._create_output_section(self.right_splitter); self.right_splitter.addWidget(output_section_widget)
        return right_area

    def _create_editor_section(self, parent_widget: QWidget) -> QWidget:
        """Creates the top-right section (editor, variables, notes, output var, buttons)."""
        editor_section_widget = QWidget(parent_widget); editor_section_layout = QVBoxLayout(editor_section_widget); editor_section_layout.setContentsMargins(0, 0, 0, 0); editor_section_layout.setSpacing(10)
        editor_label = QLabel("Prompt Editor (use {variable_name} for placeholders):"); self.prompt_editor = QTextEdit(); self.prompt_editor.setPlaceholderText("Enter prompt with {variables}..."); editor_section_layout.addWidget(editor_label); editor_section_layout.addWidget(self.prompt_editor, 1) # Editor gets vertical stretch

        # Variables Input Area (Scrollable GroupBox)
        self.variables_groupbox = QGroupBox("Prompt Variables"); self.variables_groupbox.setObjectName("VariablesGroupBox")
        variables_layout = QVBoxLayout(); scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_content_widget = QWidget(); self.variables_form_layout = QFormLayout(scroll_content_widget); self.variables_form_layout.setContentsMargins(5, 5, 5, 5); self.variables_form_layout.setSpacing(8); scroll_area.setWidget(scroll_content_widget); variables_layout.addWidget(scroll_area); self.variables_groupbox.setLayout(variables_layout); self.variables_groupbox.setVisible(False)
        editor_section_layout.addWidget(self.variables_groupbox) # Add below editor

        # Details Layout (Form for Category, Notes, Output Variable)
        details_layout = QFormLayout(); self.category_input = QLineEdit(); self.category_input.setPlaceholderText("Optional category...")
        self.notes_input = QTextEdit(); self.notes_input.setPlaceholderText("Optional notes..."); self.notes_input.setMaximumHeight(80) # Limit notes height
        self.output_variable_input = QLineEdit(); self.output_variable_input.setPlaceholderText("e.g., summary_result (optional)"); self.output_variable_input.setToolTip("Output variable name for prompt chaining")
        details_layout.addRow(QLabel("Category:"), self.category_input); details_layout.addRow(QLabel("Notes:"), self.notes_input); details_layout.addRow(QLabel("Output Variable Name:"), self.output_variable_input); editor_section_layout.addLayout(details_layout)

        # Editor Buttons (Save, Clear)
        editor_buttons_layout = QHBoxLayout(); self.save_button = QPushButton("Save Prompt"); self.clear_button = QPushButton("New / Clear Editor"); editor_buttons_layout.addStretch(); editor_buttons_layout.addWidget(self.save_button); editor_buttons_layout.addWidget(self.clear_button); editor_section_layout.addLayout(editor_buttons_layout)
        return editor_section_widget

    def _create_output_section(self, parent_widget: QWidget) -> QWidget:
        """Creates the bottom-right section (output, controls, generate buttons)."""
        output_widget = QWidget(parent_widget); output_layout = QVBoxLayout(output_widget); output_layout.setContentsMargins(0, 0, 0, 0); output_layout.setSpacing(10)

        # Output Display Area
        output_label = QLabel("Generated Output:"); self.generated_output = QTextEdit(); self.generated_output.setReadOnly(True); self.generated_output.setPlaceholderText("Generated text will appear here..."); output_layout.addWidget(output_label); output_layout.addWidget(self.generated_output, 1) # Output gets vertical stretch

        # Controls Group (Model, Parameters)
        controls_layout = QVBoxLayout(); controls_layout.setSpacing(8)
        # Model Selection Row
        model_selection_layout = QHBoxLayout(); model_label = QLabel("Model:"); self.model_selection_combo = QComboBox(); self.model_selection_combo.setEditable(False); self.model_selection_combo.setMinimumWidth(250); self.model_selection_combo.setToolTip("Models loaded in LM Studio (Refresh)"); self.model_selection_combo.addItem(DEFAULT_MODEL_FALLBACK); self.refresh_models_button = QPushButton("Refresh"); self.refresh_models_button.setToolTip("Fetch loaded models"); self.refresh_models_button.setObjectName("RefreshModelsButton"); self.refresh_models_button.setFixedWidth(80); model_selection_layout.addWidget(model_label); model_selection_layout.addWidget(self.model_selection_combo, 1); model_selection_layout.addWidget(self.refresh_models_button); controls_layout.addLayout(model_selection_layout)
        # Parameters Row
        params_layout = QHBoxLayout(); params_layout.setSpacing(10); temp_label = QLabel("Temp:"); self.temperature_spinbox = QDoubleSpinBox(); self.temperature_spinbox.setRange(0.0, 2.0); self.temperature_spinbox.setSingleStep(0.1); self.temperature_spinbox.setValue(DEFAULT_TEMPERATURE); self.temperature_spinbox.setDecimals(2); self.temperature_spinbox.setToolTip("Generation temperature"); self.temperature_spinbox.setFixedWidth(70); max_tokens_label = QLabel("Max Tokens:"); self.max_tokens_spinbox = QSpinBox(); self.max_tokens_spinbox.setRange(1, 16384); self.max_tokens_spinbox.setSingleStep(64); self.max_tokens_spinbox.setValue(DEFAULT_MAX_TOKENS); self.max_tokens_spinbox.setToolTip("Max tokens"); self.max_tokens_spinbox.setFixedWidth(90); params_layout.addWidget(temp_label); params_layout.addWidget(self.temperature_spinbox); params_layout.addStretch(); params_layout.addWidget(max_tokens_label); params_layout.addWidget(self.max_tokens_spinbox); params_layout.addStretch(); controls_layout.addLayout(params_layout)
        output_layout.addLayout(controls_layout) # Add controls block below output area

        # Output Buttons (Generate, Copy)
        output_buttons_layout = QHBoxLayout(); self.generate_button = QPushButton("Generate Response"); self.generate_button.setObjectName("GenerateButton"); self.copy_output_button = QPushButton("Copy Output to Editor"); output_buttons_layout.addWidget(self.generate_button); output_buttons_layout.addStretch(); output_buttons_layout.addWidget(self.copy_output_button); output_layout.addLayout(output_buttons_layout)
        return output_widget