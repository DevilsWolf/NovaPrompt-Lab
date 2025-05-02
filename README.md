# NovaPrompt-Lab


# NovaPrompt Lab

**A Desktop GUI for Enhanced Interaction with Local LLMs via LM Studio**

NovaPrompt Lab provides a user-friendly interface to manage, test, and execute prompts with Large Language Models running locally through the [LM Studio](https://lmstudio.ai/) API server. It focuses on prompt organization, templating, and building simple prompt chains (workflows).

---

**[Insert Screenshot Here]**

*![Screenshot_149](https://github.com/user-attachments/assets/71f964d5-d091-42dc-bb52-78e8b12ba9a5)*

*![Screenshot_150](https://github.com/user-attachments/assets/1e90a480-8ce2-4aa4-940a-9d0855c96bd8)*


---

## Features

*   **Prompt Management:**
    *   Save and load prompts with associated categories and notes.
    *   Filter prompts by category.
    *   Search prompts by keyword in text, category, or notes.
    *   Preview selected prompts.
*   **LLM Interaction:**
    *   Connect to a running LM Studio API server.
    *   Select the currently loaded model from LM Studio (with refresh).
    *   Adjust generation parameters (Temperature, Max Tokens).
    *   Generate responses with **streaming output** for better responsiveness.
    *   Concise output prompting to minimize conversational filler from the LLM.
    *   Copy generated output back to the editor easily.
*   **Prompt Templating:**
    *   Define prompts with variables using `{variable_name}` syntax.
    *   Dynamically generated input fields for filling in variables.
    *   Built-in scrollable guide with examples (Help -> Prompt Templating Guide).
*   **Workflow Engine (Basic):**
    *   Define workflows as ordered sequences of saved prompts.
    *   Assign output variable names (`output_variable_name`) to prompt steps.
    *   Automatic variable passing: Output from one step (`{output_var}`) is substituted into the next step's template if it uses the same variable name (`{output_var}`).
    *   Dialog for entering required initial inputs for the workflow.
    *   Execute workflows step-by-step.
    *   View step progress and intermediate outputs in the "Workflow Log" panel (View -> Workflow Log).
*   **Modern UI:**
    *   Customizable dark theme using QSS (`style.qss`).
    *   Refactored codebase (`app.py`, `ui.py`, `workers.py`, `database.py`).

## Prerequisites

1.  **[LM Studio](https://lmstudio.ai/):** You MUST have LM Studio installed and running. NovaPrompt Lab *connects* to LM Studio; it doesn't run models itself.
2.  **Python:** Version 3.8 or higher recommended (developed with 3.10+). [Download Python](https://www.python.org/downloads/).
3.  **pip:** Python's package installer (usually included with Python).

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/novaprompt-lab.git # Replace with your repo URL
    cd novaprompt-lab
    ```

2.  **Create and Activate a Virtual Environment (Highly Recommended):**
    *   **Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    *   **macOS / Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *(This isolates project dependencies)*

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Run LM Studio:**
    *   Launch the LM Studio application.
    *   **Load a Model:** Select the model you want to use from the list and click "Load model". Ensure it finishes loading.
    *   **Start API Server:** Go to the "Server" tab (often denoted by `<->`) and click "Start Server". By default, it runs on `http://localhost:1234`.
2.  **NovaPrompt Lab Configuration:**
    *   **API URL:** The application currently assumes the LM Studio API is running at `http://localhost:1234/v1`. This is defined as `LM_STUDIO_API_BASE_URL` near the top of `app.py`. If your LM Studio server uses a different port, you'll need to modify this constant for now. (Future improvement: Make this configurable via Settings).
    *   **Default Parameters:** Default Temperature and Max Tokens are set as constants near the top of `app.py`. These are used as initial values in the UI.

## Usage

1.  **Activate Virtual Environment** (if not already active):
    *   Windows: `.\venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`
2.  **Run the Application:**
    ```bash
    python app.py
    ```
3.  **Refresh Models:** Once the app opens, click the "Refresh" button next to the "Model" dropdown to fetch models currently loaded in LM Studio. Select the one you want to use.
4.  **Manage Prompts:** Use the "Prompts" tab to load, save, delete, filter, and search your prompts.
5.  **Use Templates:** Write `{variable_name}` in the editor. Fill in the values in the "Prompt Variables" section that appears.
6.  **Generate:** Adjust parameters (Temp, Max Tokens) and click "Generate Response".
7.  **Manage Workflows:** Use the "Workflows" tab to create sequences of saved prompts. Remember to set the "Output Variable Name" on prompts whose output should feed into the next step.
8.  **Run Workflows:** Select a workflow and click "Run Workflow". Provide initial inputs if prompted. Monitor progress in the "Workflow Log" (toggle via View menu).

## Troubleshooting

*   **Connection Errors ("Error fetching models", "API Request Error"):**
    *   Verify LM Studio is running.
    *   Verify the LM Studio API server is started (on the `<->` tab in LM Studio).
    *   Check that `LM_STUDIO_API_BASE_URL` in `app.py` matches the address shown in LM Studio Server logs (usually `http://localhost:1234/v1`).
    *   Check your firewall isn't blocking localhost connections (less common).
*   **Model Not Found (During Generation/Workflow):**
    *   Make sure the desired model is fully loaded in LM Studio *before* clicking Refresh/Generate/Run Workflow.
    *   Ensure the correct model is selected in the dropdown.
*   **Variable Input Box Not Appearing/Updating:**
    *   Ensure variables use the exact `{variable_name}` syntax (only letters, numbers, underscore inside).
    *   Try typing or deleting a character in the editor to re-trigger the detection (debouncing might occasionally miss a very fast event). If issues persist after the debounce fix, please report it.
*   **Database Errors / Workflow/Prompt Not Found:**
    *   If you suspect database corruption or schema issues after code updates, you can try deleting the `prompts.db` file (this **will delete all saved prompts and workflows**) and restarting the app. A new, clean database will be created.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests. (You can expand this section later if needed).

## License

This project is licensed under the [MIT License](LICENSE). (Choose a license like MIT and create a `LICENSE` file).
