<div align="center">

# Reflective Engine
### Recursive Reflection Architecture for Self-Evolving AI

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Research_Preview-orange.svg)]()

*A framework enabling self-evolving, context-aware AI systems designed for local deployment.*

[**Read the Research Paper**](./Reflective_Engine_research_paper.pdf) · [**Evidence Review**](./Reflective_Engine_corrected.pdf) · [**Report Bug**](../../issues) · [**Request Feature**](../../issues)

</div>

---

## 📖 Overview

**Reflective Engine** is the reference implementation of the concepts discussed in my research paper on **Recursive Reflection Architectures**. 

Unlike traditional static chains-of-thought, this engine implements a dynamic feedback loop where the model can "reflect" on its own outputs, modify its internal context state, and evolve its response strategy in real-time. It is designed to be lightweight enough for **local hobbyist hardware** while mimicking the metacognitive patterns found in larger frontier models.

##🧪 Meta-Experiment (AI-Assisted Development)

Note: This codebase is itself part of the experiment described in the accompanying research.

I intentionally developed much of this project using my own locally hosted AI system, **Ghost**, which implements the same recursive-reflective principles proposed in the paper.

**Objective:**  
To evaluate whether a recursive-reflective model can maintain architectural coherence, consistency, and intent across a multi-file, non-trivial codebase.

**Result:**  
The repository represents the outcome of that experiment. While I guided structure, intent, and review, large portions of the implementation were produced through an experimental AI-assisted workflow designed to test self-correcting generation loops.

This project should therefore be read both as software *and* as empirical evidence supporting the proposed architecture.

##📐 Research Transparency (Use of AI Tools)

Parts of the accompanying research paper—particularly some mathematical reasoning and verification steps—were developed with the assistance of **Ghost**, a locally hosted AI system I am building as part of this research.

I used the system as a reasoning aid and self-consistency checker during derivations, not as an autonomous author. All final formulations, interpretations, and conclusions were reviewed, validated, and are my responsibility.

This process also served as an informal evaluation of how reflective AI systems affect reasoning quality and problem-solving performance.


## ✨ Key Features

* **🧠 Recursive Reflection Loop:** The core engine allows the model to critique and refine its own outputs before final generation.
* **📂 Local-First Design:** Optimized for local inference (compatible with llama.cpp / Ollama backends).
* **🔄 Self-Evolving Context:** The system maintains a dynamic memory state that adapts based on user interaction depth.
* **🔌 Dual-Interface:**
    * **CLI:** Direct interaction via `reflective_enginev2.py`.
    * **Web UI:** A clean React-based frontend for visual interaction.

## 🏗️ Architecture

The project is structured into three main components:

1.  **Core Engine (`reflective_enginev2.py`):** The standalone Python implementation of the recursive loop.
2.  **Backend (`/backend`):** API server handling state management and model orchestration.
3.  **Frontend (`/frontend`):** A modern web interface for visualizing the "thought process" of the engine.

## 🚀 Getting Started

### Prerequisites

* **Python 3.10+**
* **Node.js 16+** (for frontend)
* **Git**

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/TRXAlpha/Reflective-Engine.git](https://github.com/TRXAlpha/Reflective-Engine.git)
    cd Reflective-Engine
    ```

2.  **Set up the Python Environment**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Run the Standalone Engine**
    To test the reflection logic directly in your terminal:
    ```bash
    python reflective_enginev2.py
    ```

### Running the Web Interface

1.  **Start the Backend**
    ```bash
    cd backend
    python server.py
    ```

2.  **Start the Frontend**
    ```bash
    # Open a new terminal
    cd frontend
    npm install
    npm run dev
    ```

## 📄 The Research

This repository accompanies the paper **"Reflective Engine: A Local Inference-Time Framework for Iterative Self-Evaluation in Language Model Applications."**

The current paper presents the project as a research-preview artifact. It documents the implemented reflective loop and explicitly avoids unsupported benchmark claims.

👉 **[Download research paper](./Reflective_Engine_research_paper.pdf)**  
👉 **[Download evidence review](./Reflective_Engine_corrected.pdf)**

## 🗺️ Roadmap

- [x] v1.0: Proof of Concept (Python Script)
- [x] v2.0: Core Engine Refactor (`reflective_enginev2.py`)
- [ ] v2.5: API Integration with Local LLMs (Ollama)
- [ ] v3.0: Persistent Long-Term Memory (Vector Store)

## 🤝 Contributing

This is a research project, but contributions are welcome!
1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📜 License

Distributed under the GNU General Public License v3.0. See `LICENSE` for more information.

---

<div align="center">
    
**Built with ❤️ by [TRXAlpha](https://github.com/TRXAlpha)**

</div>
