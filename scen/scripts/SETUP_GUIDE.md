# ScenGen Setup Guide for Windows and Linux

This guide is written so any student can run ScenGen on their own machine.

## Requirements for all users

- Python `3.9`
- `pip`
- `adb` in `PATH`
- `Ollama`
- local model `llama3:8b`
- the full ScenGen project folder on your machine

## Windows

Open **Command Prompt** and move into your own project folder:

```bat
cd /d C:\path\to\your\ScenGen
```

Run setup:

```bat
scripts\setup_scengen_from_scratch.bat
```

Install the local LLM once:

```bat
ollama pull llama3:8b
```

Make sure Ollama is running, then run:

```bat
ollama serve
adb devices
scripts\start_scengen.bat A34 S8
```

## Linux

Open a terminal and move into your own project folder:

```bash
cd /path/to/your/ScenGen
```

Make the scripts executable once:

```bash
chmod +x scripts/setup_scengen_from_scratch.sh scripts/start_scengen.sh run_scengen_here.sh
```

Run setup:

```bash
./scripts/setup_scengen_from_scratch.sh
```

Install the local LLM once:

```bash
ollama pull llama3:8b
```

Make sure Ollama is running, then run:

```bash
ollama serve
adb devices
./scripts/start_scengen.sh A34 S8
```

## Example IDs already present in `testbot/conf.json`

- `A34` = `Calculator-2`
- `S8` = `calculation`

Students can open `testbot/conf.json` and choose any other `APP-ID` and `SCENARIO-ID`.

## Direct run without helper scripts

### Windows

```bat
call venv\Scripts\activate.bat
python test.py A34 S8
```

### Linux

```bash
source venv/bin/activate
python test.py A34 S8
```
