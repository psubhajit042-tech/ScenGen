# ScenGen: LLM-guided Scenario-based GUI Testing

> Terminology: `LLM` in file/class names (e.g. `llm.py`, `LLMChatManager`, `SCENGEN_LLM`) means the local **Qwen2.5-VL vision-language model (VLM)** served by Ollama. The runtime reasoning loop is multimodal (screenshots + widget lists).

### Environment Setup

To set up the environment for this project, please follow the steps below:

1. **Python Version**: Ensure that your Python version is 3.9. You can check your Python version by running the following command in your terminal: `python --version`.
2. **Install Dependencies**: Use the `pip` package manager to install the necessary dependencies listed in the `requirements.txt` file. Run the following command in your project directory: `pip install -r requirements.txt`.
3. **Local VLM Setup (Ollama + Qwen2.5-VL)**: This project uses a local Ollama-served **Qwen2.5-VL** vision-language model for its LLM/VLM reasoning loop (default `qwen2.5vl:7b`, previously `llama3:8b`).
   - Install Ollama from https://ollama.com/download, then:
     ```bash
     ollama pull qwen2.5vl:7b
     ollama serve
     ```
     Keep `ollama serve` running before starting ScenGen.
   - The model is **multimodal** — screenshots are sent to the VLM as base64 images (Ollama `images` field) alongside the structured widget lists produced by computer vision (UIED + PaddleOCR).
   - `qwen2.5vl:7b` needs roughly 8GB+ VRAM/RAM. For lower VRAM use `qwen2.5vl:3b` via the `SCENGEN_LLM` environment variable. The endpoint can be overridden with `SCENGEN_OLLAMA_URL` (default `http://localhost:11434/api/generate`).
   - Verify the setup with `python smoke_test_vlm.py` (checks loading-check + action-decision schemas against the running model).
4. **ADB Installation**: The system requires the Android Debug Bridge (ADB) tool to control Android devices via ADB commands. You can verify that ADB is correctly installed by running the following command: `adb --version`.

### Project Structure

The project's codebase is organized into the following directories and key files:

- **test.py**: The entry point. It builds the `Device`/`DeviceManager`, creates the `TestAgent`, and runs the test loop. Usage: `python test.py <APP-ID> <SCENARIO-ID>`.
- **core.py**: Contains the `TestAgent`, the main orchestrator that executes scenario-based automated GUI testing as a finite state machine (`INITIALIZED → OBSERVING → EXECUTING → LOAD-CHECKING → EFFECT-CHECKING → END-CHECKING`, with a `CORRECTING` recovery state).
- **roles folder**: Contains the five role agents coordinated by `TestAgent`:
  - `observer.py` — captures screenshots and extracts GUI widgets.
  - `decider.py` — decides the next action via the VLM (Qwen2.5-VL) and matches/confirms the target widget. Includes deterministic planners for `calculate` and camera "take photo" scenarios.
  - `executor.py` — converts decided actions into ADB commands (tap / input / scroll / back / wait / launch / stop).
  - `supervisor.py` — validates each step (loading check, effect check, end check) using VLM visual reasoning over the screenshots.
  - `recorder.py` — records the action history and exports replayable test scripts and VLM chat logs (`LLMChatManager` conversation history).
- **prompt folder**: Contains modules that construct the prompts used for VLM interactions, including predefined templates and functions for generating prompts dynamically.
- **uied folder**: Built upon the project [UIED](https://github.com/MulongXie/UIED), this directory focuses on extracting GUI widgets using traditional computer vision algorithms and OCR models. `detect.py` (`WidgetDetector`) orchestrates component detection (`detect_compo/`), PaddleOCR text detection (`detect_text/`), and merging (`detect_merge/`) into the widget list used by the Observer agent.
- **device.py**: Handles control and management of the devices under test via ADB (interactions, commands, responses).
- **llm.py** (`LLMChatManager` VLM client): Interfaces with the local Ollama-served VLM (`qwen2.5vl:7b`), managing per-stage chat contexts, multimodal image attachments (base64 screenshots via Ollama's `images` field), JSON-schema structured output enforcement, and response normalisation.
- **memory.py**: Implements the context memory required by the agents, managing screenshots, detected elements, and performed actions across iterations.
- **config.py**: Loads the app and scenario registry from `apps.json` and `scenarios.json` (falls back to `conf.json` if those files are absent).
- **apps.json / scenarios.json**: The app and test-scenario registry consumed by `config.py`.
- **utils.py**: Shared helpers for JSON extraction, punctuation removal, and text similarity matching.
- **logger.py**: File + console logging (writes to `agent.log`).
- **ocr_lab folder**: An isolated OCR experiment lane for benchmarking the OCR model and fine-tuning a custom PaddleOCR recognition model. It does not change the live ScenGen runtime. See `ocr_lab/README.md`.
- **scripts folder**: Setup and launch helpers (`setup_scengen_from_scratch.bat/.sh`, `start_scengen.bat/.sh`, `run_scengen_here.bat/.sh`).
- **demo_train_run.py**: A classroom-safe, standalone simulation of the project loop (see below).

### Configuration and Execution

To configure and run the project, please follow these steps: (Suppose the project root directory is `/scengen`)

1. **Add Configuration Information**:

   Add the configuration information for the apps and the test scenarios in `testbot/apps.json` and `testbot/scenarios.json`. Ensure that the relevant apps are installed on the device under test.

   Here is an example of the app entry (`apps.json`):

   ```json
   [
     {
       "id": "A1",
       "name": "QQ Mail",
       "package": "com.tencent.androidqqmail",
       "launch-activity": "com.tencent.qqmail.launcher.desktop.LauncherActivity"
     }
   ]
   ```

   Here is an example of the scenario entry (`scenarios.json`):

   ```json
   [
     {
       "id": "S1",
       "name": "send email",
       "description": "send an email to friend",
       "extra-info": {
         "friend's email": "example@example.com",
         "email subject": "example",
         "email content": "example"
       }
     }
   ]
   ```

   The `extra-info` field is optional and can be added based on the actual testing needs. A legacy single-file `testbot/conf.json` format is still supported as a fallback when `apps.json`/`scenarios.json` are absent.

2. **Paths are auto-resolved** (no manual path configuration needed):

   - The widget-detection output directory is derived automatically from the screenshot path (screenshots under `data/input` produce outputs under `data/output`). See `testbot/uied/detect.py`.
   - OCR model folders are auto-located relative to the project root. You can override them with environment variables:

   | Environment variable | Default | Purpose |
   |---|---|---|
   | `SCENGEN_OCR_MODEL` | `ch_ppocr_mobile_v2.0_xx` | Which registered PaddleOCR model to use at runtime |
   | `SCENGEN_OCR_DET_DIR` | `ch_ppocr_mobile_v2.0_det_infer` | Detection model folder |
   | `SCENGEN_OCR_CLS_DIR` | `ch_ppocr_mobile_v2.0_cls_infer` | Direction-classifier model folder |
   | `SCENGEN_OCR_REC_DIR` | `ch_ppocr_mobile_v2.0_rec_infer` | Recognition model folder |
   | `SCENGEN_FINETUNED_REC_DIR` | `ocr_lab/models/candidate_finetuned/my_rec_infer` | Recognition model used by the `finetuned_rec` entry |

3. Run the Project

   To execute the tests, run the `test.py` script with the appropriate APP ID and SCENARIO ID:

   ```
   python test.py <APP-ID> <SCENARIO-ID>
   ```

   (Replace `<APP-ID>` and `<SCENARIO-ID>` with the IDs you configured in `apps.json` / `scenarios.json`). You can also use the helper script, e.g. `scripts/start_scengen.bat A34 S8`.

   **Note:** the project contains two parallel, identical copies of the `testbot` package — the one under `scen/` and the one at the repository root. The `test.py` at the same level as each copy imports that copy, so keep edits in sync across both.

### Evaluation

**The runtime uses a vision-language model (VLM).** The model (`qwen2.5vl:7b` via Ollama) is multimodal: it receives the task description, the performed-actions history, the UIED+PaddleOCR widget lists, **and the actual screenshots** (base64-encoded via Ollama's `images` field) on every reasoning call. Supervisor checks (loading / effect / end) receive one to three ordered screenshots; prompts state the image order explicitly. Structured output is enforced with per-stage JSON schemas sent through Ollama's `format` parameter.

Quantitative, metric-based evaluation exists only for the OCR model in the `ocr_lab/` lane (char-accuracy benchmarks vs. ground truth and PaddleOCR `eval.py`). `demo_train_run.py` prints simulated metrics for classroom presentation only. See `ARCHITECTURE.md` for details.

### Classroom Demo File

This repository also includes `demo_train_run.py` for classroom presentations.

- It is a safe, standalone, training-style simulation.
- It does **not** retrain the OCR model or the VLM (Qwen2.5-VL).
- It does **not** modify the real ScenGen inference pipeline.
- It only helps explain the real project loop in an epoch/iteration format.

Example:

```bash
python demo_train_run.py
python demo_train_run.py --epochs 2 --scenario "calculate 8+5"
```
