# Dockerfile Optimization Pipeline

An AI-powered tool that analyzes, optimizes, and improves Dockerfiles using Google's Gemini LLM. The tool automatically identifies security issues, performance problems, and best practice violations, then generates optimized Dockerfiles with improvements.

## What This Project Does

This project provides a comprehensive Dockerfile optimization pipeline that:

1. **Analyzes** Dockerfiles to identify:
   - Security risks and vulnerabilities
   - Performance issues
   - Missing best practices
   - Optimization opportunities

2. **Fixes** Dockerfiles by applying:
   - Security improvements
   - Performance optimizations
   - Best practice recommendations
   - Image size reductions

3. **Validates** fixes by comparing original vs optimized Dockerfiles

4. **Tests** by building Docker images and comparing:
   - Image sizes
   - Build times
   - Layer efficiency
   - Wasted space reduction

5. **Processes** multiple repositories in batch mode for large-scale analysis

## Features

- **AI-Powered Analysis**: Uses Google Gemini LLM for intelligent Dockerfile analysis
- **Security Focus**: Identifies and fixes security vulnerabilities
- **Performance Optimization**: Reduces image sizes and improves build efficiency
- **Comprehensive Reports**: Detailed analysis with metrics and comparisons
- **Batch Processing**: Process multiple repositories in parallel
- **History Tracking**: View and compare past optimization runs

## Prerequisites

- Python 3.8 or higher
- Docker installed and running
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey)) [Steps here](GENERATE_GEMINI_KEY.md)

## Installation

1. **Clone the repository** (if you haven't already):
   ```bash
   cd CIS-580
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your API key**:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
   
   Or create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your-api-key-here
   ```

## Running the Streamlit App

The Streamlit app provides a web-based interface for the Dockerfile optimization pipeline.

### Start the App

```bash
streamlit run streamlit_app.py
```

The app will automatically open in your browser at `http://localhost:8501`

### What the Streamlit App Does

The Streamlit app provides two main modes:

#### 1. **Single Repository Mode**
- Process one repository at a time
- Step-by-step workflow visualization:
  - **Analyze**: Identifies issues in the Dockerfile
  - **Fix**: Generates an optimized version
  - **Validate**: Compares original vs optimized scores
  - **Test**: Builds and tests both images
- View detailed results including:
  - Security, efficiency, and best practice scores
  - Issue recommendations
  - Original vs optimized Dockerfile comparison
  - Build metrics and image size comparisons

#### 2. **Batch Processing Mode**
- Process multiple repositories from a file
- Parallel processing with configurable workers
- Comprehensive results with:
  - Static analysis (dive analysis) results
  - Dynamic analysis (LLM) results
  - Combined comparison charts
  - Export results to JSON or CSV
- History tracking for past runs

### Using the App

1. **Configure Settings** (in the sidebar):
   - Enter your Gemini API Key
   - Select the model (default: `gemini-2.5-flash-lite`)
   - Set build timeout
   - Choose to skip test stage if needed

2. **Single Mode**:
   - Enter path to `docker_repos.txt` file
   - Click "Start Pipeline"
   - View results as they appear

3. **Batch Mode**:
   - Switch to "batch" mode
   - Enter path to `docker_repos.txt` file
   - Set max repos and parallel workers
   - Click "Process All Repos"
   - Monitor progress and view results in tabs

### Input File Format

Create a `docker_repos.txt` file with one repository URL per line:

```
https://github.com/user/repo1
https://github.com/user/repo2
https://github.com/user/repo3
```

## Project Structure

```
CIS-580/
├── streamlit_app.py          # Main Streamlit web application
├── batch_repo_processor.py   # Batch processing engine
├── llm_agents/               # LLM-based analysis modules
│   ├── dockerfile_pipeline.py
│   ├── dockerfile_llm_analyzer.py
│   ├── dockerfile_fixer.py
│   └── dockerfile_validator.py
├── docker_image_analyzer.py  # Docker image analysis
├── dive_analyzer.py          # Dive-based image analysis
├── image_builder.py          # Docker image building utilities
├── results_manager.py        # Results storage and export
├── history_manager.py        # Analysis history tracking
└── rate_limiter.py           # API rate limiting
```

## Additional Tools

- **Knowledge Base Manager**: `python -m llm_agents.kb_manager` - Manage the knowledge base of best practices
- **Docker Image Analyzer**: `python docker_image_analyzer.py` - Standalone Docker image analysis CLI

## Notes

- The app requires Docker to be running for building and testing images
- API rate limits are automatically managed
- Results are saved to `batch_results.json` and `analysis_history.json`
- Cloned repositories are automatically cleaned up after processing

Team - 
1. Sundar Swaminathan
2. Ritesh R. Honnalli
3. Grishma Pochana
4. Mohammed Ariful Islam
