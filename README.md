# Foam-Agent  

## Introduction  

**Foam-Agent** is an AI-driven automation system designed to enhance the efficiency of **OpenFOAM** workflows. By leveraging **retrieval-augmented generation (RAG), reinforcement learning (RL), and multi-agent collaboration**, OpenFOAM Agent optimizes the process of case setup, execution, and analysis.  

This system **reduces manual intervention**, allowing engineers to **focus on simulation insights** rather than repetitive file management. Whether you're running large-scale simulations or optimizing workflows, OpenFOAM Agent provides a **scalable and intelligent** solution.  

## Features  

### 🔍 **Enhanced Retrieval System**  
- **Unlimited file length support** for retrieving large datasets.  
- **Hierarchical retrieval** covering case files, directory structures, and dependencies.  
- **Keyword-based indexing** for efficient case retrieval.  
- **Metadata-driven database control** for precise search and filtering.  

### 🤖 **AI-Powered Workflow Optimization**  
- **Dynamic execution flow using LangGraph**, enabling intelligent task management.  
- **Structured responses with Pydantic formatting** for consistency.  
- **Self-learning system** that adapts based on past case performance.  

### 🏆 **Smart Search & Execution Strategies**  
- **Neural-Guided Monte Carlo Tree Search (MCTS)** for optimizing case execution.  
- **Supervised Fine-Tuning (SFT) and Reinforcement Learning (RL)** for continuous improvement.  
- **Physics-aware RL models** to refine simulation accuracy.  

### 🛠️ **Autonomous Decision-Making**  
- **Determines when to save, run, and review cases** without manual input.  
- **Automatically modifies and refines simulation files** based on results.  
- **Multi-agent collaboration** for splitting and managing tasks efficiently.  

### 🌍 **Seamless Integration & Extensibility**  
- **File upload and case management support.**  
- **Web-based interface for interactive controls.**  
- **ChatGPT extensions for intelligent assistance.**  

## Getting Started  

Clone the repository and install dependencies:  

```bash
git clone https://github.com/csml-rpi/Foam-Agent.git

cd Foam-Agent
conda env create -f environment.yml
