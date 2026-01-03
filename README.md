<div align="center">

# Reflective Engine
### Recursive Reflection Architecture for Self-Evolving AI

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Research_Preview-orange.svg)]()

*A framework enabling self-evolving, context-aware AI systems designed for local deployment.*

[**Read the Research Paper**](./Reflective_Engine.pdf) · [**Report Bug**](../../issues) · [**Request Feature**](../../issues)

</div>

---

## 📖 Overview

**Reflective Engine** is the reference implementation of the concepts discussed in my research paper on **Recursive Reflection Architectures**. 

Unlike traditional static chains-of-thought, this engine implements a dynamic feedback loop where the model can "reflect" on its own outputs, modify its internal context state, and evolve its response strategy in real-time. It is designed to be lightweight enough for **local hobbyist hardware** while mimicking the metacognitive patterns found in larger frontier models.

## 🧪 Meta-Experiment & Disclaimer

> **Note:** This entire codebase serves as a stress test for the architecture it proposes.

To verify the limits of recursive reflection, **this project was primarily coded using my own private AI model**, which utilizes the very principles described in the attached research paper. 

* **Objective:** To test if a recursive-reflective model can maintain architectural coherence over a multi-file complex project.
* **Result:** The code you see here is the output of that experiment, demonstrating the practical capability of self-correcting generation flows.
* *While the architecture is robust, please review the code with the understanding that it is the product of an experimental autonomous coding workflow.*

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
    python app.py
    ```

2.  **Start the Frontend**
    ```bash
    # Open a new terminal
    cd frontend
    npm install
    npm run dev
    ```

## 📄 The Research

This repository accompanies the paper **"Reflective Engine: Architectures for Recursive Self-Correction."**

> **Abstract:** *Current LLM architectures suffer from hallucination propagation in long-context windows. This paper proposes a recursive architecture where...*

👉 **[Download full PDF](./Reflective_Engine.pdf)**

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
