# OpenAI Agents SDK: A Code-Intensive Intro

In this **presentation-only course**, I cover the OpenAI Agents SDK using Python and JupyterLab:

* creating agents and running them with `Runner`
* conversation state, streaming and guardrails
* hosted, local and custom tools: function tools, image generation, file search (RAG), code interpreter, MCP servers, the computer tool and the shell tool
* running a local open-weight model via LiteLLM and Ollama
* adding real-time voice to an agent with GPT-Live

Many attendees like to run examples in parallel. If you run into software issues during class, I will not have time to debug them live, but I am happy to help after class. E-mail me at paul@deitel.com.

---

## Pre-Class Checklist

Complete these steps (discussed below) to run the notebooks locally:

1. Install Anaconda or Python 3.14.
2. Get the course code from GitHub.
3. Run the setup script from the course folder.
4. Create and store your OpenAI API key in the `OPENAI_API_KEY` environment variable.
5. Launch JupyterLab from the course folder.

I'll briefly review these steps in the notebook `01-intro-and-setup.ipynb` in class.

---

## Course Notebooks

* **Part 1 — Intro/Setup:** `01`
* **Part 2 — OpenAI Agents SDK:** `02-00` through `02-05-10`
* **Part 3 — Wrap-Up and Additional References:** `03-01` through `03-03`

---

## Required Software

### Python

Recommended:

* [Anaconda](https://www.anaconda.com/download)

Alternative:

* Python 3.14 (not 3.15 yet — LiteLLM, used by `02-05-09`, doesn't support it) from [python.org](https://www.python.org/downloads/), Homebrew, `pyenv`, or another Python distribution

**Note**  
* I tested the demos with Python 3.14, and the setup scripts require it
* Python 3.15 is not supported yet because LiteLLM (used by `02-05-09`) requires Python below 3.15
* The Anaconda setup installs Python 3.14 for you

### Google Chrome (Computer Tool demo)

`02-05-07` drives your installed **Google Chrome** through Playwright so you can watch the agent browse. If Chrome is not installed, set `BROWSER_CHANNEL = None` in that notebook to use the Chromium that the setup script installs.

### Graphviz

Graphviz is used for Agents SDK graph visualizations.

* Anaconda setup installs Graphviz automatically.
* If you use `pip`/`venv`, install [Graphviz](https://graphviz.org/download/) separately and make sure the `dot` executable is on your `PATH`.

#### Internet Access

OpenAI APIs are online web services, so the examples require Internet access.

---

## Download the Course Code & Notebooks

Either download and unzip the repository from GitHub:

> https://github.com/pdeitel/Building-Agents-with-the-OpenAI-Python-Agents-SDK-A-Code-Intensive-Intro

Then open a terminal in the unzipped folder.

Or clone the repository:

```bash
git clone https://github.com/pdeitel/Building-Agents-with-the-OpenAI-Python-Agents-SDK-A-Code-Intensive-Intro.git
cd Building-Agents-with-the-OpenAI-Python-Agents-SDK-A-Code-Intensive-Intro
```

All setup commands below must be run from the course's root folder: the folder that contains both `README.md` and the `setup/` folder.

---

## Setup — Anaconda Users (Recommended)

The setup script:

* creates a conda environment named `deitel-openai-agents` (or updates it if it already exists)
* installs the OpenAI Python SDK with realtime support for GPT-Live: `openai[realtime]`
* installs the OpenAI Agents SDK: `openai-agents`
* installs JupyterLab and registers the `Python (deitel-openai-agents)` kernel
* installs Graphviz support for Agents SDK workflow visualizations
* installs Playwright Chromium browser support for the Computer Tool demo (if we have time)
* installs `yfinance` (and its `pandas` and `numpy` dependencies) for the financial research demo
* installs `litellm` for the local-model demo (`02-05-09`)
* installs `sounddevice` for microphone and speaker audio in the GPT-Live voice demo

### macOS

```bash
bash setup/setup_mac.sh
```

### Windows

Open **Anaconda Prompt** or **Anaconda PowerShell**, navigate to the course folder, then run:

```bat
setup\setup_windows.bat
```

### Updating or using a different environment name

Rerun the same script at any time to update `deitel-openai-agents` to the course's current package versions. The default name keeps this course separate from the `deitel-openai` environment used by my earlier OpenAI course. To use a different name, pass it as the first argument:

```bash
bash setup/setup_mac.sh my-env-name
```

```bat
setup\setup_windows.bat my-env-name
```

Then use that name wherever these instructions say `deitel-openai-agents`.

---

## Setup — Python/pip Users

**Use these instructions only if you are not using Anaconda.** The macOS pip setup has been tested; the Windows pip setup has not.

### macOS / Linux

Install Python 3.14 and Graphviz first if needed:

```bash
# macOS with Homebrew
brew install python@3.14 graphviz

# Debian/Ubuntu Linux (Python 3.14 from python.org, your distribution or pyenv)
sudo apt install graphviz
```

Then run this from the course folder:

```bash
bash setup/setup_pip_mac.sh
```

### Windows

Install Python 3.14 from [python.org](https://www.python.org/downloads/) and Graphviz from [graphviz.org/download](https://graphviz.org/download/) first. Make sure `dot.exe` is on your `PATH`.

Then open **Command Prompt** or **PowerShell**, navigate to the course folder, and run:

```bat
setup\setup_pip_windows.bat
```

The pip setup does not use Conda. It creates (or updates) a local `.venv` virtual environment in the course folder, installs packages into it and registers the `Python (deitel-openai-agents)` kernel. On Windows it uses the `py` launcher that the python.org installer provides, so it finds Python 3.14 even if a different `python` is first on your `PATH`.

Rerun the same script at any time to update `.venv` to the course's current package versions. To register the kernel under a different name, pass it as the first argument:

```bash
bash setup/setup_pip_mac.sh my-kernel-name
```

```bat
setup\setup_pip_windows.bat my-kernel-name
```

---

## Checking Your Setup

Each setup script ends by running `setup/check_setup.py`, which prints a pass/fail line for each requirement: Python version, packages, Graphviz, Playwright's Chromium, Google Chrome, microphone and speakers, and your API key. Run it again any time from the course folder with the course environment activated:

```bash
python setup/check_setup.py
```

---

## OpenAI Developer API Key

The OpenAI APIs are online web services and do not provide a free tier for API usage. To run the code, you need:

* an OpenAI developer account
* an OpenAI API key

### Get an API Key

1. Sign in at [platform.openai.com](https://platform.openai.com).
2. Go to the API keys page in your project settings.
3. Press **+ Create new secret key**.
4. Copy the key immediately. It is shown only once.

### Store the Key in an Environment Variable

The notebooks read your key from the `OPENAI_API_KEY` environment variable.

Do not paste API keys into notebooks or source files. OpenAI recommends keeping API keys secret, using environment variables rather than hardcoding keys, monitoring usage, and rotating keys if you suspect exposure:

> https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety

### macOS / Linux

Add this line to `~/.zshrc` or `~/.bash_profile`, replacing `YourAPIKey` with your actual key:

```bash
export OPENAI_API_KEY="YourAPIKey"
```

Then reload the shell:

```bash
source ~/.zshrc
```

If you use a different shell startup file, update that file instead.

### Windows

1. Close any open Command Prompt, PowerShell or Anaconda Prompt windows.
2. In the taskbar's **Search** field, enter `SystemPropertiesAdvanced`, then press Enter.
3. In the **System Properties** dialog, press **Environment Variables...**.
4. Under **User variables**, press **New...**.
5. Variable name: `OPENAI_API_KEY`
6. Variable value: paste your API key.
7. Press **OK** to save, then press **OK** to close the dialog.
8. Open a new terminal before launching JupyterLab.

---

## Launch JupyterLab From the Course Folder

### Anaconda

```bash
conda activate deitel-openai-agents
jupyter lab
```

If a notebook does not have a kernel selected, choose the **Python (deitel-openai-agents)** kernel.

### Python/pip on macOS / Linux

```bash
source .venv/bin/activate
jupyter lab
```

### Python/pip on Windows

```bat
.venv\Scripts\activate
jupyter lab
```

---

## Vector Stores for `02-05-03` and `02-05-10`

The book-concierge demos search two vector stores in **my** OpenAI account. To run those notebooks yourself, create your own from the PDFs in `resources/pdfs_for_rag/` (each book's preface, table of contents and index):

1. Sign in at [platform.openai.com/storage](https://platform.openai.com/storage) and select the **Vector stores** tab.
2. Press **+ Create**, name the store `jhtp12`, then **+ Add files** and upload `jhtp_preface.pdf`, `jhtpTOC.pdf` and `jhtpIX.pdf`.
3. Create a second store named `IntroToPython1` and upload `PyCDS_preface.pdf`, `PyCDSTOC.pdf` and `PyCDSIX.pdf`.
4. Copy each store's ID (`vs_...`) into the `JHTP_VS_ID` and `PYTHON_VS_ID` constants near the top of `02-05-03` and `02-05-10`.

Indexing takes seconds to a few minutes. Vector store storage is billed by OpenAI, so delete the stores when you no longer need them.

---

## OPTIONAL Setup for `02-05-09` — Local LLM via LiteLLM + Ollama

This demo runs an open-source LLM model locally rather than using a hosted OpenAI model, showing that the OpenAI Agents SDK is model agnostic. It uses the Agents SDK's `LitellmModel` adapter, which reaches Ollama (and 100+ other providers) through LiteLLM.

**The model is approximately an 8 GB download so this is entirely optional.** The demo was tested on a MacBook Pro M2 Max with 96 GB of unified memory. On less powerful hardware, inference will be significantly slower and tool-calling reliability may vary.

### LiteLLM is in the main environment

The main setup scripts install LiteLLM, so `02-05-09` uses the same environment and kernel as every other notebook. LiteLLM 1.108.0 is the first release that works with the `openai` 3.x the Agents SDK requires (earlier releases required `openai` 2.x). Until 1.108.0 is released, the course pins its release candidate, `litellm==1.108.0rc1`.

### Ollama

1. Install [Ollama](https://ollama.com/download).
2. Pull the model used in the demo:
   ```bash
   ollama pull deepseek-r1:14b
   ```
3. Start Ollama before running the notebook:
   ```bash
   ollama serve
   ```
---

## OPTIONAL: GPT-Live Voice Demo (`02-05-10`)

This demo adds a real-time voice front end to the book concierge from `02-05-03` using OpenAI's GPT-Live voice model. I'll demo it if we have time. To run it yourself, you need:

* a microphone and **headphones** — GPT-Live listens while it speaks, so through speakers it hears itself and interrupts its own answers
* an OpenAI API account above the Free usage tier — GPT-Live voice time costs $0.05 per minute, plus the backend model and tool usage
* your own vector stores — see **Vector Stores for `02-05-03` and `02-05-10`** above
* JupyterLab running on your own computer — the notebook's kernel opens the microphone and speakers, so hosted or remote Jupyter environments won't work

The course setup installs everything else. End a session by saying "goodbye" or by choosing **Kernel > Interrupt Kernel**.

---

## Troubleshooting

**`OPENAI_API_KEY` not found** — Restart your terminal, Anaconda Prompt, PowerShell or JupyterLab after setting the environment variable. JupyterLab inherits environment variables from the shell that launched it.

**`conda activate` not recognized on macOS** — Initialize conda for your shell: `conda init zsh` or `conda init bash`, then open a new terminal.

**Graphviz `dot` not found** — Install Graphviz and make sure the `dot` command is on your `PATH`. The Anaconda setup installs Graphviz automatically; the `pip`/`venv` setup checks for it before creating the environment.

**Playwright browser does not launch** — Run `python -m playwright install chromium` again from the activated environment, then retry.

**`02-05-05` cannot connect to an MCP server** — That demo uses public, third-party MCP servers (`weather.chukai.io`, `geocoder.chukai.io` and `nws.caseyjhand.com`) that I do not control. If one is down or rate-limited, the demo fails until it is back; there is nothing to fix locally.

**Local LLMs running in Ollama can be slow in `02-05-09`** — This is expected on most consumer hardware. The demo is illustrative.

**No microphone input in `02-05-10`** — On macOS, allow microphone access for the app you used to launch JupyterLab (for example, Terminal) in **System Settings > Privacy & Security > Microphone**, then restart JupyterLab.

**The concierge keeps interrupting itself in `02-05-10`** — Use headphones. For a demo through room speakers, pass `echo_guard=True` to `run_live_voice_agent`; you won't be able to interrupt the concierge while it speaks.

---

&copy; 2026 by Deitel & Associates, Inc. All Rights Reserved.
