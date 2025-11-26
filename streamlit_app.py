import streamlit as st
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import time
import pandas as pd
from datetime import datetime
from queue import Queue
from threading import Thread

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from llm_agents.dockerfile_pipeline import (
    DockerfilePipeline,
    get_first_repo_from_file,
    clone_repo,
    delete_repo
)
from llm_agents.dockerfile_llm_analyzer import find_dockerfiles
from batch_repo_processor import process_all_repos
from results_manager import save_results, load_results, get_results_summary, export_to_csv
from history_manager import (
    load_history, 
    add_run_to_history, 
    load_results_from_history,
    delete_history_record,
    get_history_summary
)
from rate_limiter import get_rate_limiter

def process_repo_from_file(
    repos_file_path: str,
    api_key: str,
    model: str,
    build_timeout: int,
    skip_test: bool,
    first_only: bool = True
) -> Dict[str, Any]:
    if not os.path.exists(repos_file_path):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_path = os.path.join(parent_dir, repos_file_path)
        if os.path.exists(parent_path):
            repos_file_path = parent_path
        else:
            raise FileNotFoundError(f"Repositories file not found: {repos_file_path}")
    
    repo_url = get_first_repo_from_file(repos_file_path)
    if not repo_url:
        raise ValueError("No valid repository URL found in file.")
    
    pipeline = DockerfilePipeline(
        api_key=api_key,
        model=model,
        build_timeout=build_timeout
    )
    
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    repos_dir = os.path.join(current_file_dir, "cloned_repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    repo_path = clone_repo(repo_url, repos_dir)
    
    try:
        dockerfiles = find_dockerfiles(repo_path)
        if not dockerfiles:
            raise ValueError(f"No Dockerfiles found in {repo_path}")
        
        if first_only:
            dockerfiles = dockerfiles[:1]
        
        dockerfile_path = dockerfiles[0]
        results = pipeline.optimize_dockerfile(dockerfile_path, skip_test=skip_test)
        
        results["repo_url"] = repo_url
        results["repo_path"] = repo_path
        results["dockerfiles_found"] = len(dockerfiles)
        results["repos_file"] = repos_file_path
        
        return results
    
    finally:
        if os.path.exists(repo_path):
            delete_repo(repo_path)

st.set_page_config(
    page_title="Dockerfile Optimization Pipeline",
    layout="wide"
)

st.markdown("""
<style>
    .workflow-container {
        display: flex;
        justify-content: space-around;
        align-items: center;
        padding: 20px;
        margin: 20px 0;
    }
    .workflow-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        position: relative;
    }
    .step-circle {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 10px;
        border: 3px solid;
        transition: all 0.3s;
    }
    .step-circle.pending {
        background-color: #f0f0f0;
        border-color: #ccc;
        color: #666;
    }
    .step-circle.active {
        background-color: #4CAF50;
        border-color: #45a049;
        color: white;
        animation: pulse 2s infinite;
    }
    .step-circle.completed {
        background-color: #2196F3;
        border-color: #1976D2;
        color: white;
    }
    .step-circle.failed {
        background-color: #f44336;
        border-color: #d32f2f;
        color: white;
    }
    .step-arrow {
        font-size: 30px;
        color: #ccc;
        margin: 0 10px;
    }
    .step-label {
        font-size: 12px;
        text-align: center;
        max-width: 100px;
        margin-top: 5px;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .output-container {
        margin-top: 20px;
        padding: 15px;
        border-radius: 5px;
        background-color: #f9f9f9;
    }
</style>
""", unsafe_allow_html=True)

def get_step_status(step_name: str, results: Dict[str, Any]) -> str:
    if not results:
        return "pending"
    
    stages = results.get("stages", {})
    stage_result = stages.get(step_name, {})
    
    if step_name not in stages:
        return "pending"
    
    success = stage_result.get("success")
    if success is True:
        return "completed"
    elif success is False:
        return "failed"
    elif stage_result.get("skipped"):
        return "pending"
    else:
        return "active"

def format_output(data: Any, max_length: int = 1000) -> str:
    if isinstance(data, dict):
        return json.dumps(data, indent=2, default=str)
    elif isinstance(data, str):
        if len(data) > max_length:
            return data[:max_length] + "...\n[Truncated]"
        return data
    else:
        return str(data)

def get_prompts_from_results(results: Dict[str, Any]) -> Dict[str, str]:
    """Extract prompts used in LLM pipeline from results.
    
    Args:
        results: Pipeline results dictionary
        
    Returns:
        Dictionary with prompt types as keys and prompt text as values
    """
    prompts = {}
    
    # Analysis stage prompts
    analysis_stage = results.get("stages", {}).get("analysis", {})
    if analysis_stage.get("success"):
        # These are the prompts from dockerfile_llm_analyzer.py
        prompts["analysis_system_prompt"] = """You are an expert Docker and container specialist. Your role is to help improve Dockerfile quality by analyzing:
1. Dockerfile structure and best practices
2. Performance and efficiency improvements
3. Optimization opportunities
4. Code quality and maintainability
5. Image size reduction techniques
6. Build process improvements

Provide structured, actionable insights to help developers create better Dockerfiles.
Focus on practical recommendations and real-world improvements."""
        
        # User prompt template (would need actual Dockerfile content to fill)
        prompts["analysis_user_prompt_template"] = """Analyze this Dockerfile and identify issues. Return JSON with the issues you find.

Dockerfile:
```
{dockerfile_content}
```

Return JSON with this structure:
{
    "security_risks": ["list of security concerns"],
    "performance_issues": ["list of performance problems"],
    "optimization_opportunities": ["optimization suggestions"],
    "runtime_concerns": ["runtime problems"],
    "best_practices_missing": ["missing best practices"],
    "estimated_wasted_space_kb": <number>,
    "complexity_score": <1-10, where 10 is most complex>,
    "maintainability_score": <1-10, where 10 is most maintainable>,
    "overall_assessment": "summary of Dockerfile quality",
    "recommendations": [{"category": "security|performance|best_practice|optimization", "severity": "critical|high|medium|low", "message": "specific actionable recommendation with exact fix", "instruction_line": <line number or null>}]
}"""
    
    # Fix stage prompts
    fix_stage = results.get("stages", {}).get("fix", {})
    if fix_stage.get("success"):
        fix_result = fix_stage.get("result", {})
        scores = results.get("original_analysis", {}).get("scores", {})
        
        prompts["fix_system_prompt"] = f"""You are a precise Docker optimization specialist. Your goal is to fix ONLY the specific issues identified in the analysis, using the recommendations as your primary guide.

CURRENT DOCKERFILE STATUS:
- Overall Score: {scores.get('overall_score', 0)}%
- Security Score: {scores.get('security_score', 0)}%
- Efficiency Score: {scores.get('efficiency_score', 0)}%
- Best Practices Score: {scores.get('best_practices_score', 0)}%

CRITICAL RULES:
1. Use the SPECIFIC RECOMMENDATIONS as your PRIMARY source for fixes - they contain exact instructions
2. For each recommendation, make the exact change it suggests at the specified line
3. Do NOT introduce new security risks, performance issues, or complexity
4. Preserve ALL original functionality - the Dockerfile must work exactly as before
5. Make targeted, surgical changes - only modify what needs to be fixed"""
        
        prompts["fix_user_prompt_template"] = """You must fix the Dockerfile by applying the SPECIFIC RECOMMENDATIONS listed above. Each recommendation tells you exactly what to change.

ORIGINAL DOCKERFILE:
```
{original_dockerfile}
```

{analysis_summary}

CRITICAL: Return ONLY the complete fixed Dockerfile. It MUST:
- Start with FROM (required - do not omit this!)
- Include ALL original instructions (FROM, SHELL, ENV, WORKDIR, VOLUME, etc.)
- Only modify the specific lines that need fixing
- Preserve all non-modified instructions exactly as they were
- Be a complete, valid Dockerfile

Return ONLY the raw Dockerfile starting with FROM. No explanations, no markdown, no code blocks."""
    
    return prompts


def display_llm_prompts_tab(results: Dict[str, Any]):
    """Display LLM prompts tab content.
    
    Args:
        results: Pipeline results dictionary
    """
    st.header("LLM Prompts Used in Pipeline")
    st.markdown("This section shows all prompts used in the LLM analysis and fixing stages.")
    
    prompts = get_prompts_from_results(results)
    
    if not prompts:
        st.info("No prompts available. Run the pipeline first to see prompts.")
        return
    
    # Analysis Prompts
    with st.expander("Analysis Stage Prompts", expanded=True):
        st.subheader("System Prompt")
        if "analysis_system_prompt" in prompts:
            st.code(prompts["analysis_system_prompt"], language="text")
            st.button("Copy System Prompt", key="copy_analysis_system", 
                     on_click=lambda: st.write("Copied to clipboard!"))
        
        st.subheader("User Prompt Template")
        if "analysis_user_prompt_template" in prompts:
            st.code(prompts["analysis_user_prompt_template"], language="text")
            st.button("Copy User Prompt Template", key="copy_analysis_user",
                     on_click=lambda: st.write("Copied to clipboard!"))
    
    # Fix Prompts
    with st.expander("Fix Stage Prompts", expanded=False):
        st.subheader("System Prompt")
        if "fix_system_prompt" in prompts:
            st.code(prompts["fix_system_prompt"], language="text")
            st.button("Copy System Prompt", key="copy_fix_system",
                     on_click=lambda: st.write("Copied to clipboard!"))
        
        st.subheader("User Prompt Template")
        if "fix_user_prompt_template" in prompts:
            st.code(prompts["fix_user_prompt_template"], language="text")
            st.button("Copy User Prompt Template", key="copy_fix_user",
                     on_click=lambda: st.write("Copied to clipboard!"))


def display_workflow(results: Dict[str, Any] = None, current_step: Optional[str] = None):
    steps = [
        {"name": "analysis", "label": "1. Analyze", "icon": ""},
        {"name": "fix", "label": "2. Fix", "icon": ""},
        {"name": "validation", "label": "3. Validate", "icon": ""},
        {"name": "test", "label": "4. Test", "icon": ""}
    ]
    
    html = '<div class="workflow-container">'
    for i, step in enumerate(steps):
        if current_step == step["name"]:
            status = "active"
        else:
            status = get_step_status(step["name"], results) if results else "pending"
        
        status_class = f"step-circle {status}"
        
        html += f'''
        <div class="workflow-step">
            <div class="{status_class}">
                {step["label"]}
            </div>
        </div>
        '''
        
        if i < len(steps) - 1:
            prev_status = get_step_status(steps[i]["name"], results) if results else "pending"
            arrow_color = "#4CAF50" if prev_status in ["completed", "active"] else "#ccc"
            html += f'<div class="step-arrow" style="color: {arrow_color};">→</div>'
    
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def main():
    st.title("Dockerfile Optimization Pipeline")
    
    # History section
    with st.expander("📊 Analysis History", expanded=False):
        _display_history_section()
    
    st.markdown("---")
    
    # Initialize session state
    if "pipeline_results" not in st.session_state:
        st.session_state.pipeline_results = None
    if "pipeline_running" not in st.session_state:
        st.session_state.pipeline_running = False
    if "batch_results" not in st.session_state:
        st.session_state.batch_results = []
    if "batch_running" not in st.session_state:
        st.session_state.batch_running = False
    if "processing_mode" not in st.session_state:
        st.session_state.processing_mode = "single"
    if "max_workers" not in st.session_state:
        st.session_state.max_workers = 1
    
    with st.sidebar:
        st.header("Configuration")
        
        # Mode selection
        processing_mode = st.radio(
            "Processing Mode",
            options=["single", "batch"],
            index=0 if st.session_state.processing_mode == "single" else 1,
            help="Single: Process one repo. Batch: Process all repos from file."
        )
        st.session_state.processing_mode = processing_mode
        
        api_key = st.text_input(
            "Gemini API Key",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="Enter your Gemini API key or set GEMINI_API_KEY environment variable"
        )
        
        model = st.selectbox(
            "Model",
            options=["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-3-pro-preview", "gemini-1.5-flash", "gemini-1.5-pro"],
            index=0,
            help="Select the Gemini model to use (or set GEMINI_MODEL env var). If gemini-2.5-flash-lite is selected and quota is exceeded, will automatically fallback to gemini-2.0-flash-lite."
        )
        
        # Show fallback info
        if model == "gemini-2.5-flash-lite":
            st.info("ℹ️ **Auto-fallback enabled**: If quota is exceeded, will automatically switch to `gemini-2.0-flash-lite`")
        
        skip_test = st.checkbox(
            "Skip Test Stage",
            value=False,
            help="Skip the Docker build/test stage"
        )
        
        build_timeout = st.number_input(
            "Build Timeout (seconds)",
            min_value=60,
            max_value=600,
            value=300,
            step=30
        )
    
        if processing_mode == "batch":
            max_repos = st.number_input(
                "Max Repos to Process",
                min_value=1,
                max_value=1000,
                value=100,
                help="Maximum number of repositories to process (for testing)"
            )
            max_workers = st.slider(
                "Parallel Workers",
                min_value=1,
                max_value=10,
                value=st.session_state.max_workers,
                key="max_workers_slider",
                help="Number of repositories to process in parallel (higher = faster but more resource intensive). ⚠️ WARNING: Values > 1 require more memory. Use 1 for small EC2 instances (<4GB RAM) to prevent OOM errors."
            )
            st.session_state.max_workers = max_workers
            if max_workers > 1:
                st.warning(f"⚠️ Parallel processing enabled: {max_workers} workers. Ensure your EC2 instance has sufficient memory (≥4GB RAM recommended). OOM errors may occur on smaller instances.")
            else:
                st.info("ℹ️ Sequential processing (1 worker). Safe for all instance sizes, but slower.")
            
            cleanup_images = st.checkbox(
                "Cleanup Images",
                value=False,
                help="Remove Docker images after processing"
            )
    
    if processing_mode == "single":
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("Repositories File")
            repos_file_path = st.text_input(
                "Enter the path to docker_repos.txt file",
                value="docker_repos.txt",
                placeholder="docker_repos.txt",
                label_visibility="collapsed",
                help="Path to the file containing repository URLs (one per line)"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            start_button = st.button("Start Pipeline", type="primary", width="stretch")
    
    if "selected_step" not in st.session_state:
        st.session_state.selected_step = None
    
    st.markdown("### Workflow Status")
    current_step = st.session_state.get("current_step")
    display_workflow(st.session_state.pipeline_results, current_step)
    
    # Single repo processing logic
    if processing_mode == "single":
        if start_button and repos_file_path:
            if not api_key:
                st.error("Please provide a Gemini API Key in the sidebar")
            else:
                st.session_state.pipeline_running = True
                st.session_state.pipeline_results = None
                
                progress_placeholder = st.empty()
                with progress_placeholder.container():
                    st.info("Pipeline started...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        status_text.info("Processing repository from file...")
                        progress_bar.progress(10)
                        
                        results = process_repo_from_file(
                            repos_file_path=repos_file_path,
                            api_key=api_key,
                            model=model,
                            build_timeout=build_timeout,
                            skip_test=skip_test,
                            first_only=True
                        )

                        progress_bar.progress(100)
                        status_text.success("Pipeline completed!")
                        
                        st.session_state.pipeline_results = results
                        st.session_state.pipeline_running = False
                        st.session_state.current_step = None
                        
                        time.sleep(1)
                        progress_placeholder.empty()
                        
                        st.rerun()
                        
                    except Exception as e:
                        progress_bar.progress(0)
                        status_text.error(f"Error: {str(e)}")
                        st.session_state.pipeline_running = False
                        st.session_state.current_step = None
                        import traceback
                        st.exception(e)
        
        # Display single repo results outside the button handler so they
        # persist after st.rerun()
        if st.session_state.pipeline_results:
            _display_single_repo_results(st.session_state.pipeline_results)
        elif st.session_state.pipeline_running:
            st.info("Pipeline is running... Please wait.")

    else:
        # Batch processing mode
        st.subheader("Batch Processing Mode")
        st.markdown("Process all repositories from the file and compare original vs optimized images.")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            repos_file_path = st.text_input(
                "Repositories File Path",
                value="docker_repos.txt",
                help="Path to the file containing repository URLs (one per line)"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            start_batch_button = st.button("Process All Repos", type="primary", width="stretch")
        
        if start_batch_button and repos_file_path:
            if not api_key:
                st.error("Please provide a Gemini API Key in the sidebar")
            else:
                st.session_state.batch_running = True
                st.session_state.batch_results = []
                
                progress_placeholder = st.empty()
                with progress_placeholder.container():
                    st.info("Batch processing started...")
                    
                    # Active workers indicator
                    workers_indicator = st.empty()
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # Thread-safe queue for progress updates from worker threads
                        progress_queue = Queue()
                        processing_done = False
                        results_container = {"results": None, "error": None}
                        
                        # Rate limit status display
                        rate_status_placeholder = st.empty()
                        
                        def progress_callback(msg, current=None, total=None):
                            """Thread-safe progress callback - puts updates in queue."""
                            try:
                                progress_queue.put({
                                    "msg": msg,
                                    "current": current,
                                    "total": total
                                })
                            except:
                                # If queue operations fail, just print (safe from any thread)
                                print(f"Progress: {msg}")
                        
                        # Start processing in a separate thread
                        def run_processing():
                            try:
                                fallback_model = None
                                if model == "gemini-2.5-flash-lite":
                                    fallback_model = "gemini-2.0-flash-lite"
                                
                                results = process_all_repos(
                                    repos_file=repos_file_path,
                                    api_key=api_key,
                                    model=model,
                                    build_timeout=build_timeout,
                                    skip_test=skip_test,
                                    cleanup_repo=True,
                                    cleanup_images=cleanup_images,
                                    max_repos=max_repos,
                                    max_workers=max_workers,
                                    rpm_limit=15,
                                    tpm_limit=250000,
                                    rpd_limit=1000,
                                    progress_callback=progress_callback,
                                    fallback_model=fallback_model,
                                    auto_cleanup_docker=True,
                                    docker_cleanup_interval=10
                                )
                                results_container["results"] = results
                                progress_queue.put({"done": True})
                            except Exception as e:
                                import traceback
                                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                                results_container["error"] = error_msg
                                progress_queue.put({"error": True})
                        
                        # Start processing thread
                        processing_thread = Thread(target=run_processing, daemon=True)
                        processing_thread.start()
                        
                        # Poll queue and update UI from main thread (Streamlit-safe)
                        last_update_time = time.time()
                        while not processing_done:
                            try:
                                # Check for updates (non-blocking)
                                update_received = False
                                while not progress_queue.empty():
                                    try:
                                        update = progress_queue.get_nowait()
                                        update_received = True
                                        
                                        if update.get("done"):
                                            processing_done = True
                                            break
                                        elif update.get("error"):
                                            processing_done = True
                                            break
                                        else:
                                            # Update UI from main thread only
                                            msg = update.get("msg", "")
                                            current = update.get("current")
                                            total = update.get("total")
                                            
                                        if current and total:
                                            progress = int((current / total) * 100)
                                            progress_bar.progress(progress)
                                            
                                            # Extract active workers from message if present
                                            active_workers = 0
                                            if "Active workers:" in msg:
                                                try:
                                                    active_part = msg.split("Active workers:")[1].split("]")[0].strip()
                                                    active_workers = int(active_part)
                                                except:
                                                    pass
                                            
                                            # Update active workers indicator
                                            with workers_indicator.container():
                                                col1, col2, col3 = st.columns([1, 2, 1])
                                                with col2:
                                                    if active_workers > 0:
                                                        st.metric(
                                                            "🔄 Active Parallel Workers",
                                                            active_workers,
                                                            delta=f"Max: {max_workers}",
                                                            help=f"Currently processing {active_workers} repositories in parallel (max: {max_workers})"
                                                        )
                                                    else:
                                                        st.metric(
                                                            "🔄 Active Parallel Workers",
                                                            0,
                                                            help="No active workers"
                                                        )
                                            
                                            # Display status
                                            clean_msg = msg.split("(Active workers:")[0].strip() if "(Active workers:" in msg else msg
                                            status_text.info(f"[{current}/{total}] {clean_msg}")
                                                
                                            # Update rate limit status periodically
                                            if time.time() - last_update_time > 2:  # Update every 2 seconds
                                                    try:
                                                        rate_limiter = get_rate_limiter()
                                                        if rate_limiter:
                                                            status = rate_limiter.get_status()
                                                            with rate_status_placeholder.container():
                                                                st.caption("📊 API Rate Limit Status")
                                                                col1, col2, col3 = st.columns(3)
                                                                with col1:
                                                                    st.metric(
                                                                        "RPM",
                                                                        f"{status['rpm_used']}/{status['rpm_limit']}",
                                                                        delta=f"{status['rpm_percent']:.1f}%"
                                                                    )
                                                                with col2:
                                                                    st.metric(
                                                                        "TPM",
                                                                        f"{status['tpm_used']/1000:.1f}K/{status['tpm_limit']/1000:.0f}K",
                                                                        delta=f"{status['tpm_percent']:.1f}%"
                                                                    )
                                                                with col3:
                                                                    st.metric(
                                                                        "RPD",
                                                                        f"{status['rpd_used']}/{status['rpd_limit']}",
                                                                        delta=f"{status['rpd_percent']:.1f}%"
                                                                    )
                                                            last_update_time = time.time()
                                                    except:
                                                        pass
                                        else:
                                            status_text.info(msg)
                                    except:
                                        break
                                
                                # Check if thread finished
                                if not processing_thread.is_alive():
                                    if not processing_done:
                                        # Thread finished - check for final results
                                        if results_container["error"]:
                                            raise Exception(results_container["error"])
                                        elif results_container["results"] is not None:
                                            processing_done = True
                                        else:
                                            # Wait a bit more for final message
                                            time.sleep(0.5)
                                            if progress_queue.empty() and results_container["results"] is None:
                                                st.warning("Processing completed but no results received")
                                                processing_done = True
                                
                                if not processing_done:
                                    time.sleep(0.2)  # Small delay to avoid busy waiting
                                    
                            except Exception as e:
                                st.error(f"Error updating progress: {str(e)}")
                                processing_done = True
                                break
                        
                        # Get final results
                        if results_container["error"]:
                            raise Exception(results_container["error"])
                        
                        results = results_container["results"]
                        if results is None:
                            raise Exception("Processing completed but no results were returned")
                        
                        # Log results summary for debugging
                        successful = sum(1 for r in results if r.get("success"))
                        failed = len(results) - successful
                        if failed > 0:
                            # Show some error examples
                            error_examples = [r.get("error", "Unknown error") for r in results[:5] if not r.get("success")]
                            status_text.warning(f"Processing completed: {successful} successful, {failed} failed. Sample errors: {error_examples[:3]}")
                        else:
                            status_text.success(f"Batch processing completed! Processed {len(results)} repositories.")
                        
                        progress_bar.progress(100)
                        
                        st.session_state.batch_results = results
                        st.session_state.batch_running = False
                        
                        # Save results
                        output_file = "batch_results.json"
                        save_results(results, output_file)
                        
                        # Add to history
                        history_record = add_run_to_history(
                            results=results,
                            repos_file=repos_file_path,
                            model=model,
                            skip_test=skip_test,
                            max_repos=max_repos if 'max_repos' in locals() else None
                        )
                        st.success(f"Results saved to {output_file} and added to history.")
                        
                        time.sleep(1)
                        progress_placeholder.empty()
                        
                        st.rerun()
                        
                    except Exception as e:
                        progress_bar.progress(0)
                        status_text.error(f"Error: {str(e)}")
                        st.session_state.batch_running = False
                        import traceback
                        st.exception(e)
        
        # Display batch results in tabs
        if st.session_state.batch_results:
            _display_batch_results_tabs(st.session_state.batch_results)
        elif st.session_state.batch_running:
            st.info("Batch processing is running... Please wait.")

def _display_single_repo_results(results: Dict[str, Any]):
    """Display results for single repo processing."""
    st.markdown("---")
    
    if "repo_url" in results:
        st.info(f"**Repository:** {results.get('repo_url')} | **Dockerfiles Found:** {results.get('dockerfiles_found', 1)}")
    
    st.subheader("Step Outputs")
    
    stages = results.get("stages", {})
    
    with st.expander("Step 1: Analysis", expanded=False):
        analysis_stage = stages.get("analysis", {})
        if analysis_stage.get("success"):
            analysis_result = analysis_stage.get("result", {})
            scores = analysis_result.get("scores", {})
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Overall Score", f"{scores.get('overall_score', 0):.1f}%")
            with col2:
                st.metric("Security Score", f"{scores.get('security_score', 0):.1f}%")
            with col3:
                st.metric("Efficiency Score", f"{scores.get('efficiency_score', 0):.1f}%")
            with col4:
                st.metric("Best Practices", f"{scores.get('best_practices_score', 0):.1f}%")
            llm_analysis = analysis_result.get("llm_analysis", {})
            if llm_analysis.get("success"):
                llm_data = llm_analysis.get("data", {})
                st.markdown("#### Issues Found")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Security Risks:** {len(llm_data.get('security_risks', []))}")
                with col2:
                    st.write(f"**Performance Issues:** {len(llm_data.get('performance_issues', []))}")
                with col3:
                    st.write(f"**Missing Practices:** {len(llm_data.get('best_practices_missing', []))}")
                recommendations = llm_data.get("recommendations", [])
                if recommendations:
                    st.markdown("#### Top Recommendations")
                    for rec in recommendations[:5]:
                        severity = rec.get("severity", "medium")
                        message = rec.get("message", "")
                        category = rec.get("category", "general")
                        st.write(f"- **[{severity.upper()}]** {category}: {message}")
            else:
                st.warning(f"LLM Analysis failed: {llm_analysis.get('error', 'Unknown error')}")
        else:
            st.error(f"Analysis failed: {analysis_stage.get('error', 'Unknown error')}")
    
    with st.expander("Step 2: Fix", expanded=False):
        fix_stage = stages.get("fix", {})
        if fix_stage.get("success"):
            fix_result = fix_stage.get("result", {})
            # Check if fix was skipped
            if fix_result.get("skipped", False) or fix_stage.get("skipped", False):
                reason = fix_result.get("reason", "Dockerfile is already optimal")
                st.info(f"**Fix Skipped:** {reason}")
                st.markdown("The Dockerfile is already excellent and doesn't need optimization.")
                if "original_dockerfile" in results:
                    st.markdown("#### Original Dockerfile (No changes needed)")
                    st.code(results.get("original_dockerfile", ""), language="dockerfile")
            else:
                fixed_dockerfile = fix_result.get("fixed_dockerfile", "")
                st.success("Dockerfile optimized successfully!")
                if "original_dockerfile" in results:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### Original Dockerfile")
                        st.code(results.get("original_dockerfile", ""), language="dockerfile")
                    with col2:
                        st.markdown("#### Optimized Dockerfile")
                        st.code(fixed_dockerfile, language="dockerfile")
                else:
                    st.markdown("#### Optimized Dockerfile")
                    st.code(fixed_dockerfile, language="dockerfile")
                st.download_button(
                    label="Download Optimized Dockerfile",
                    data=fixed_dockerfile,
                    file_name="Dockerfile.optimized",
                    mime="text/plain"
                )
        else:
            st.error(f"Fix failed: {fix_stage.get('error', 'Unknown error')}")
    
    with st.expander("Step 3: Validation", expanded=False):
        validation_stage = stages.get("validation", {})
        if validation_stage.get("success"):
            # Check if validation was skipped
            if validation_stage.get("skipped", False):
                st.info("**Validation Skipped:** No changes were made to validate.")
                st.markdown("Since the Dockerfile was already optimal, validation was skipped.")
            else:
                validation_result = validation_stage.get("result", {})
                # Check if fix was reverted
                if validation_result.get("reverted", False) or results.get("fix_reverted", False):
                    reason = results.get("revert_reason", "Fix would have decreased scores")
                    st.warning(f"**Fix Reverted:** {reason}")
                    st.markdown("The optimized Dockerfile would have made the Dockerfile worse, so the original was kept.")
                improvements = validation_result.get("improvements", {})
                st.success("Validation completed!")
                if improvements:
                    st.markdown("#### Score Improvements")
                    for key, imp in improvements.items():
                        if key in ["overall_score", "security_score", "efficiency_score", "best_practices_score"]:
                            key_name = key.replace("_", " ").title()
                            orig = imp["original"]
                            fixed = imp["fixed"]
                            diff = imp["improvement"]
                            pct = imp["percent_change"]
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.write(f"**{key_name}**")
                            with col2:
                                st.write(f"{orig:.1f} → {fixed:.1f}")
                            with col3:
                                if diff > 0:
                                    st.success(f"+{diff:.1f} ({pct:+.1f}%)")
                                elif diff < 0:
                                    st.error(f"{diff:.1f} ({pct:.1f}%)")
                                else:
                                    st.info("No change")
                    issues_comparison = validation_result.get("issues_comparison", {})
                    if issues_comparison:
                        st.markdown("#### Issues Resolved")
                        sec = issues_comparison.get("security_risks", {})
                        perf = issues_comparison.get("performance_issues", {})
                        missing = issues_comparison.get("missing_practices", {})
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(
                                "Security Risks",
                                f"{sec.get('original_count', 0)} → {sec.get('fixed_count', 0)}",
                                delta=f"-{len(sec.get('fixed', []))}"
                            )
                        with col2:
                            st.metric(
                                "Performance Issues",
                                f"{perf.get('original_count', 0)} → {perf.get('fixed_count', 0)}",
                                delta=f"-{len(perf.get('fixed', []))}"
                            )
                        with col3:
                            st.metric(
                                "Missing Practices",
                                f"{missing.get('original_count', 0)} → {missing.get('fixed_count', 0)}",
                                delta=f"-{len(missing.get('fixed', []))}"
                            )
        else:
            error = validation_stage.get("error", "Unknown error")
            st.warning(f"Validation completed with warnings: {error}")
    
    with st.expander("Step 4: Test", expanded=False):
        test_stage = stages.get("test", {})
        if test_stage.get("skipped"):
            reason = test_stage.get("reason", "Test stage was skipped")
            st.info(f"Test stage was skipped: {reason}")
        elif test_stage.get("success"):
            test_result = test_stage.get("result", {})
            st.success("Docker build and test passed!")
            col1, col2, col3 = st.columns(3)
            with col1:
                if test_result.get("build_time"):
                    st.metric("Build Time", f"{test_result.get('build_time', 0):.2f}s")
            with col2:
                if test_result.get("step_count"):
                    st.metric("Build Steps", test_result.get("step_count"))
            with col3:
                if test_result.get("final_size"):
                    st.metric("Image Size", test_result.get("final_size"))
            if test_result.get("build_output"):
                st.markdown("#### Build Output")
                st.text_area("Build Output", value=test_result.get("build_output", ""), height=200, disabled=True, label_visibility="hidden")
        else:
            error = test_stage.get("error", "Unknown error")
            st.error(f"Test failed: {error}")
            if test_stage.get("result", {}).get("build_errors"):
                st.markdown("#### Build Errors")
                st.text_area("Build Errors", value=test_stage.get("result", {}).get("build_errors", ""), height=200, disabled=True, label_visibility="hidden")
    
    st.markdown("---")
    st.subheader("Pipeline Summary")
    if results.get("success"):
        st.success("Pipeline completed successfully!")
    else:
        st.error("Pipeline completed with errors")

    
def _display_batch_results_tabs(results: List[Dict[str, Any]]):
    """Display batch results in tabs."""
    if not results:
        st.info("No results to display.")
        return

    st.info("These results have been saved to history. Expand 'Analysis History' at the top to view and reload past runs.")

    summary = get_results_summary(results)
    build_summary = results[0].get("batch_summary", {}) if results else {}
    successful_builds = build_summary.get("successful_builds", 0)
    failed_builds = build_summary.get("failed_builds", 0)
    estimated_results = build_summary.get("estimated_results", 0)
    actual_results = build_summary.get("actual_results", 0)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Repos", summary["total_repos"])
    with col2:
        st.metric("Successful Builds", successful_builds, 
                  delta=f"-{failed_builds} failed" if failed_builds > 0 else None)
    with col3:
        st.metric("Actual Results", actual_results,
                  help="Repos with full dive analysis and build comparison")
    with col4:
        st.metric("Estimated Results", estimated_results,
                  help="Repos with estimated improvements (build failed)")
    with col5:
        st.metric("Avg Size Reduction", f"{summary['avg_size_reduction_percent']:.1f}%")

    if build_summary:
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"✅ **{successful_builds}** repositories with successful builds (full dive analysis available)")
        with col2:
            if estimated_results > 0:
                st.warning(f"📊 **{estimated_results}** repositories with estimated improvements (builds failed, using LLM analysis)")

    failed_repos = [r for r in results if not r.get("success")]
    if failed_repos:
        with st.expander(f"⚠️ Failed Repositories ({len(failed_repos)})", expanded=False):
            st.warning(f"{len(failed_repos)} repositories failed to process. Check errors below:")

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Static Analysis Results",
            "Dynamic Analysis Results",
            "Combined Comparison",
            "LLM Prompts",
        ]
    )

    with tab1:
        _display_static_analysis_tab(results)

    with tab2:
        _display_dynamic_analysis_tab(results)

    with tab3:
        _display_combined_comparison_tab(results)

    with tab4:
        st.header("LLM Prompts")
        if not results:
            st.info("No results available.")
        else:
            options = list(range(len(results)))
            def _format_repo(idx: int) -> str:
                r = results[idx]
                return r.get("repo_name") or r.get("repo_url") or f"Result {idx+1}"

            selected_idx = st.selectbox(
                "Select repository to view LLM prompts:",
                options=options,
                format_func=_format_repo,
            )

            selected_result = results[selected_idx]
            dyn_analysis = selected_result.get("dynamic_analysis", {})
            llm_pipeline_results = dyn_analysis.get("llm_pipeline_results")

            if not llm_pipeline_results:
                st.info("No LLM pipeline results available for this repository.")
            else:
                display_llm_prompts_tab(llm_pipeline_results)

def _display_static_analysis_tab(results: List[Dict[str, Any]]):
    """Display static analysis results tab."""
    st.header("Static Analysis Results")
    
    table_data = []
    for result in results:
        if not result.get("success"):
            continue
        
        is_estimated = result.get("estimated", False)
        orig_img = result.get("original_image", {})
        opt_img = result.get("optimized_image", {})
        comparison = result.get("comparison", {})
        
        if is_estimated:
            estimation = comparison.get("estimation", {})
            size_reduction_pct = estimation.get("size_reduction_percent", 0)
            size_reduction_bytes = estimation.get("size_reduction_bytes", 0)
            efficiency_imp = estimation.get("efficiency_improvement")
            orig_size = None  # Not available for estimated
            opt_size = None
            orig_dive = {}
            opt_dive = {}
        else:
            orig_size = orig_img.get("size_bytes", 0)
            opt_size = opt_img.get("size_bytes", 0)
            size_reduction_pct = comparison.get("size_reduction_percent", 0)
            orig_dive = orig_img.get("dive_analysis", {})
            opt_dive = opt_img.get("dive_analysis", {})
            efficiency_imp = comparison.get("efficiency_improvement")
            size_reduction_bytes = comparison.get("size_reduction_bytes", 0)
        
        repo_name = result.get("repo_name", result.get("repo_url", "Unknown"))
        if is_estimated:
            repo_name = f"📊 {repo_name} (Estimated)"
        
        table_data.append({
            "Repo": repo_name,
            "Type": "Estimated" if is_estimated else "Actual",
            "Original Size (MB)": round(orig_size / (1024 * 1024), 2) if orig_size else "N/A",
            "Optimized Size (MB)": round(opt_size / (1024 * 1024), 2) if opt_size else "N/A",
            "Size Reduction %": f"~{round(size_reduction_pct, 2)}" if is_estimated and size_reduction_pct else round(size_reduction_pct, 2) if size_reduction_pct else 0,
            "Efficiency (Original)": f"{orig_dive.get('efficiency', 0):.1f}%" if orig_dive.get('efficiency') else "N/A",
            "Efficiency (Optimized)": f"{opt_dive.get('efficiency', 0):.1f}%" if opt_dive.get('efficiency') else "N/A",
            "Efficiency Improvement": f"~{efficiency_imp:+.1f}%" if is_estimated and efficiency_imp else f"{efficiency_imp:+.1f}%" if efficiency_imp else "N/A",
            "Original Layers": orig_dive.get("layer_count", 0),
            "Optimized Layers": opt_dive.get("layer_count", 0),
            "Status": "Success" if result.get("success") else "Failed"
        })
    
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, width="stretch", hide_index=True)
        
        st.subheader("Filters")
        col1, col2 = st.columns(2)
        with col1:
            min_reduction = st.slider("Min Size Reduction %", -100, 100, -100)
        with col2:
            min_efficiency = st.slider("Min Efficiency Improvement %", -50, 50, -50)
        
        efficiency_numeric = pd.to_numeric(
            df["Efficiency Improvement"].str.replace("%", "").str.replace("+", ""),
            errors="coerce"
        ).fillna(-999)
        
        filtered_df = df[
            (df["Size Reduction %"] >= min_reduction) &
            (efficiency_numeric >= min_efficiency)
        ]
        st.dataframe(filtered_df, width="stretch", hide_index=True)
    else:
        st.info("No successful results to display.")


def _display_dynamic_analysis_tab(results: List[Dict[str, Any]]):
    """Display dynamic analysis (LLM) results tab."""
    st.header("Dynamic Analysis Results")
    
    table_data = []
    for result in results:
        if not result.get("success"):
            continue
        
        dyn_analysis = result.get("dynamic_analysis", {})
        llm_results = dyn_analysis.get("llm_pipeline_results", {})
        stages = llm_results.get("stages", {})
        
        orig_analysis = stages.get("analysis", {}).get("result", {})
        orig_scores = orig_analysis.get("scores", {})
        
        validation = stages.get("validation", {}).get("result", {})
        fixed_scores = validation.get("fixed_scores", {})
        improvements = validation.get("improvements", {})
        
        overall_imp = improvements.get("overall_score", {}).get("improvement", 0)
        security_imp = improvements.get("security_score", {}).get("improvement", 0)
        efficiency_imp = improvements.get("efficiency_score", {}).get("improvement", 0)
        best_practices_imp = improvements.get("best_practices_score", {}).get("improvement", 0)
        
        table_data.append({
            "Repo": result.get("repo_name", result.get("repo_url", "Unknown")),
            "Overall Score": f"{orig_scores.get('overall_score', 0):.1f}% → {fixed_scores.get('overall_score', 0):.1f}%",
            "Overall Improvement": f"{overall_imp:+.1f}",
            "Security Improvement": f"{security_imp:+.1f}",
            "Efficiency Improvement": f"{efficiency_imp:+.1f}",
            "Best Practices Improvement": f"{best_practices_imp:+.1f}",
            "Status": "Success" if result.get("success") else "Failed"
        })
    
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No successful results to display.")


def _display_combined_comparison_tab(results: List[Dict[str, Any]]):
    """Display combined comparison tab with charts."""
    st.header("Combined Comparison")
    
    successful_results = [r for r in results if r.get("success")]
    
    if not successful_results:
        st.info("No successful results to display.")
        return
    
    # Size reduction chart
    st.subheader("Size Reduction")
    size_data = []
    for result in successful_results:
        comparison = result.get("comparison", {})
        size_reduction_pct = comparison.get("size_reduction_percent", 0)
        if size_reduction_pct:
            size_data.append({
                "Repo": result.get("repo_name", "Unknown"),
                "Size Reduction %": size_reduction_pct
            })
    
    if size_data:
        size_df = pd.DataFrame(size_data)
        st.bar_chart(size_df.set_index("Repo"))
    
    st.subheader("Export Results")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export to JSON"):
            output_file = "batch_results.json"
            save_results(results, output_file)
            st.success(f"Results exported to {output_file}")
    with col2:
        if st.button("Export to CSV"):
            output_file = "batch_results.csv"
            export_to_csv(results, output_file)
            st.success(f"Results exported to {output_file}")


def _display_history_section():
    """Display the analysis history section."""
    history = load_history()
    history_summary = get_history_summary()
    
    if not history:
        st.info("No analysis history yet. Run batch processing to create history records.")
        return
    
    st.subheader("History Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Runs", history_summary["total_runs"])
    with col2:
        st.metric("Total Repos Processed", history_summary["total_repos_processed"])
    with col3:
        st.metric("Total Space Saved", f"{history_summary['total_space_saved_mb']:.1f} MB")
    with col4:
        st.metric("Avg Size Reduction", f"{history_summary['avg_size_reduction_percent']:.1f}%")
    
    st.markdown("---")
    st.subheader("Past Runs")
    
    history_data = []
    for record in history:
        timestamp = record.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            display_time = timestamp
        
        summary = record.get("summary", {})
        history_data.append({
            "Timestamp": display_time,
            "Repos File": Path(record.get("repos_file", "")).name,
            "Model": record.get("model", "N/A"),
            "Total Repos": record.get("total_repos", 0),
            "Successful": record.get("successful_repos", 0),
            "Failed": record.get("failed_repos", 0),
            "Avg Size Reduction": f"{summary.get('avg_size_reduction_percent', 0):.1f}%",
            "Space Saved (MB)": f"{summary.get('total_size_saved_bytes', 0) / (1024 * 1024):.1f}",
            "Timestamp (ISO)": timestamp
        })
    
    if history_data:
        df = pd.DataFrame(history_data)
        
        selected_indices = st.selectbox(
            "Select a run to view details:",
            options=range(len(history_data)),
            format_func=lambda x: f"{history_data[x]['Timestamp']} - {history_data[x]['Total Repos']} repos ({history_data[x]['Successful']} successful)"
        )
        
        if selected_indices is not None:
            selected_record = history[selected_indices]
            st.markdown("---")
            st.subheader("Run Details")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Timestamp:** {history_data[selected_indices]['Timestamp']}")
                st.write(f"**Repos File:** {selected_record.get('repos_file', 'N/A')}")
                st.write(f"**Model:** {selected_record.get('model', 'N/A')}")
                st.write(f"**Skip Test:** {selected_record.get('skip_test', False)}")
            with col2:
                st.write(f"**Total Repos:** {selected_record.get('total_repos', 0)}")
                st.write(f"**Successful:** {selected_record.get('successful_repos', 0)}")
                st.write(f"**Failed:** {selected_record.get('failed_repos', 0)}")
                summary = selected_record.get("summary", {})
                st.write(f"**Avg Size Reduction:** {summary.get('avg_size_reduction_percent', 0):.1f}%")
                st.write(f"**Total Space Saved:** {summary.get('total_size_saved_bytes', 0) / (1024 * 1024):.1f} MB")
            
            # Buttons to load results or delete
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Load Results", key=f"load_{selected_indices}"):
                    timestamp = selected_record.get("timestamp")
                    results = load_results_from_history(timestamp)
                    if results:
                        st.session_state.batch_results = results
                        st.session_state.processing_mode = "batch"
                        st.success("Results loaded! Switch to batch mode to view them.")
                        st.rerun()
                    else:
                        st.error("Could not load results for this run.")
            
            with col2:
                if st.button("🗑️ Delete Run", key=f"delete_{selected_indices}"):
                    timestamp = selected_record.get("timestamp")
                    if delete_history_record(timestamp):
                        st.success("Run deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete run.")
        
        st.markdown("---")
        st.subheader("All Runs")
        display_df = df.drop(columns=["Timestamp (ISO)"])
        st.dataframe(display_df, width="stretch", hide_index=True)

if __name__ == "__main__":
    main()

