# workers.py - Worker Threads for NovaPrompt Lab

import requests
import json
import urllib.parse
import traceback
import re # Needed for VARIABLE_PATTERN

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QThread, pyqtSignal, QObject # Import QObject for type hinting

# Ensure local imports are handled correctly for type hinting
from typing import TYPE_CHECKING, List, Dict, Optional, Tuple, Any
if TYPE_CHECKING:
    from database import DatabaseManager # Import only for type hints

# Regex needed by WorkflowRunner
VARIABLE_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")

# --- Generation Worker ---
class WorkerThread(QThread):
    """Worker thread to handle STREAMING GENERATION API calls with concise prompting."""
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str, bool) # final_message, success_bool

    def __init__(self, prompt_text: str, api_base_url: str, model_name: str,
                 temperature: float, max_tokens: int,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.prompt_text = prompt_text; self.api_base_url = api_base_url; self.model_name = model_name
        self.temperature = temperature; self.max_tokens = max_tokens
        self._is_cancelled = False; self._error_occurred = False

    def run(self):
        """Executes the streaming generation API call."""
        generation_url = urllib.parse.urljoin(self.api_base_url + '/', "chat/completions")
        self._error_occurred = False; final_status_message = "Stream finished."
        try:
            system_prompt = "You are a helpful assistant that strictly follows instructions. Provide only the requested output text directly, without any introductory phrases, explanations, apologies, code blocks, or conversational filler."
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": self.prompt_text}]
            payload = {"model": self.model_name, "messages": messages, "temperature": self.temperature, "max_tokens": self.max_tokens, "stream": True}
            print(f"Sending STREAMING request to: {generation_url} Model: {self.model_name} Params: T={self.temperature}, MT={self.max_tokens}")
            response = requests.post(generation_url, json=payload, stream=True, timeout=(10, 180)); response.raise_for_status()
            print("Stream connection established.");
            for line in response.iter_lines():
                if self._is_cancelled: final_status_message = "Stream cancelled by user."; print(final_status_message); self._error_occurred = True; break
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        data_str = decoded_line[len('data: '):].strip();
                        if data_str == '[DONE]': print("SSE stream finished ([DONE] received)."); break
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {}); content_chunk = delta.get('content')
                                if content_chunk: self.chunk_received.emit(content_chunk)
                                finish_reason = data['choices'][0].get('finish_reason');
                                if finish_reason: print(f"Stream finished with reason: {finish_reason}"); final_status_message = f"Stream finished ({finish_reason})."
                        except json.JSONDecodeError: print(f"Warning: Could not decode JSON: {data_str}")
                        except Exception as e_parse: print(f"Error parsing SSE chunk: {e_parse}"); final_status_message = f"Error parsing stream data: {e_parse}"; self._error_occurred = True; break
            response.close(); print(f"Stream loop finished. Final status: {final_status_message}")
        except requests.exceptions.Timeout as e: final_status_message = f"API Request Timeout ({e})."; print(final_status_message); self._error_occurred = True
        except requests.exceptions.RequestException as e: final_status_message = f"API Request Error: {e}"; print(final_status_message); self._error_occurred = True
        except Exception as e: final_status_message = f"Unexpected streaming error: {e}\n{traceback.format_exc()}"; print(final_status_message); self._error_occurred = True
        finally: print(f"Emitting finished: Success={not self._error_occurred}, Msg='{final_status_message}'"); self.finished.emit(final_status_message, not self._error_occurred)

    def cancel(self): print("Worker thread cancellation requested."); self._is_cancelled = True

# --- Workflow Runner Thread ---
class WorkflowRunner(QThread):
    """Runs a sequence of prompts, passing outputs to subsequent steps."""
    step_started = pyqtSignal(int, str)       # step_index (0-based), step_description
    step_finished = pyqtSignal(int, str, str) # step_index, output_variable_name, output_text
    workflow_complete = pyqtSignal(str, bool) # final_output_text, success_bool
    error_occurred = pyqtSignal(str)          # error_message

    def __init__(self,
                 workflow_steps: List[int],
                 initial_variables: Dict[str, str],
                 db_manager: 'DatabaseManager', # Use forward reference type hint
                 api_base_url: str,
                 model_name: str,
                 temperature: float,
                 max_tokens: int,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        # Basic check for DatabaseManager type at runtime if needed
        if 'DatabaseManager' in globals() and db_manager is not None and not isinstance(db_manager, globals()['DatabaseManager']):
             raise TypeError("db_manager must be an instance of DatabaseManager")
        elif 'DatabaseManager' not in globals() and db_manager is not None:
             # Fallback if type hinting failed but object was passed
             print("Warning: DatabaseManager type could not be verified at runtime in WorkflowRunner.")


        self.steps = workflow_steps; self.initial_vars = initial_variables; self.db_manager = db_manager
        self.api_base_url = api_base_url; self.model_name = model_name; self.temperature = temperature
        self.max_tokens = max_tokens; self._is_cancelled = False; self._error_message = ""

    def run(self):
        """Executes the workflow step by step."""
        print("--- WorkflowRunner started ---"); step_outputs = self.initial_vars.copy(); final_output_text = ""; success = True
        try:
            for i, prompt_id in enumerate(self.steps):
                if self._is_cancelled: self._error_message = "Workflow cancelled."; success = False; break
                print(f"Workflow Step {i+1}: Fetching prompt ID {prompt_id}");
                if not self.db_manager: self._error_message = "DB Manager unavailable."; success = False; break
                prompt_data = self.db_manager.get_prompt_by_id(prompt_id)
                if not prompt_data: self._error_message = f"Prompt ID {prompt_id} not found."; success = False; break
                try: _id, prompt_template, _cat, _nts, _c, output_var_name = prompt_data
                except (ValueError, IndexError): self._error_message = f"Invalid data format for prompt ID {prompt_id}."; success = False; break

                step_description = f"Step {i+1}: {prompt_template.split(chr(10), 1)[0]}"; self.step_started.emit(i, step_description)
                current_prompt_text = prompt_template; missing_step_vars = []; required_vars = set(VARIABLE_PATTERN.findall(prompt_template))
                print(f"  Step {i+1} requires: {required_vars or '{}'}"); print(f"  Available vars: {list(step_outputs.keys())}")
                for var_name in required_vars:
                    placeholder = "{" + var_name + "}";
                    if var_name in step_outputs: current_prompt_text = current_prompt_text.replace(placeholder, step_outputs[var_name])
                    else: missing_step_vars.append(var_name)
                if missing_step_vars: self._error_message = f"Step {i+1} Error: Missing input(s): {{{', '.join(missing_step_vars)}}}."; success = False; break
                instruction_suffix = "\n\nIMPORTANT: Respond *only* with the generated text itself."; prompt_to_send = current_prompt_text.strip() + instruction_suffix
                print(f"  Executing Step {i+1}..."); step_result_text = self._execute_single_step(prompt_to_send)
                if step_result_text is None: success = False; break # Error in helper
                final_output_text = step_result_text
                if output_var_name and output_var_name.strip(): clean_output_var_name = output_var_name.strip(); print(f"  Storing output: {{{clean_output_var_name}}}"); step_outputs[clean_output_var_name] = step_result_text
                self.step_finished.emit(i, output_var_name or "[No Output Var]", step_result_text); QThread.msleep(100) # Optional delay
        except Exception as e: self._error_message = f"Unexpected Workflow Error: {e}\n{traceback.format_exc()}"; success = False
        finally:
            if success: print("--- WorkflowRunner finished successfully ---"); self.workflow_complete.emit(final_output_text, True)
            else: print(f"--- WorkflowRunner failed: {self._error_message} ---");
            if self._error_message: self.error_occurred.emit(self._error_message)
            self.workflow_complete.emit(self._error_message or "Workflow failed.", False)

    def _execute_single_step(self, prompt_to_send: str) -> str | None:
        """Calls the LLM API non-streamed and returns the text result or None on error."""
        generation_url = urllib.parse.urljoin(self.api_base_url + '/', "chat/completions")
        try:
            system_prompt = "You are a helpful assistant that strictly follows instructions. Provide only the requested output text directly, without any introductory phrases, explanations, apologies, code blocks, or conversational filler."
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt_to_send}]
            payload = {"model": self.model_name, "messages": messages, "temperature": self.temperature, "max_tokens": self.max_tokens, "stream": False}
            print(f"    Calling API (Non-Streamed): {self.model_name}"); response = requests.post(generation_url, json=payload, timeout=120); response.raise_for_status()
            response_data = response.json(); generated_text = response_data['choices'][0]['message']['content'].strip(); print(f"    Step completed."); return generated_text
        except requests.exceptions.Timeout as e: self._error_message = f"Step Error: API Timeout ({e})."; print(f"    {self._error_message}"); return None
        except requests.exceptions.RequestException as e: self._error_message = f"Step Error: API Request Error ({e})."; print(f"    {self._error_message}"); return None
        except (KeyError, IndexError, json.JSONDecodeError) as e: self._error_message = f"Step Error: Cannot parse API response ({e})."; print(f"    {self._error_message}"); return None
        except Exception as e: self._error_message = f"Step Error: Unexpected error ({e})."; print(f"    {self._error_message}\n{traceback.format_exc()}"); return None

    def cancel(self):
        """Signals the runner to stop gracefully between steps."""
        print("WorkflowRunner cancellation requested.")
        self._is_cancelled = True