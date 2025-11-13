import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional, Any


class DockerfileTester:    
    def __init__(self, build_timeout: int = 300):
        self.build_timeout = build_timeout
        self.docker_available = self._check_docker_available()
    
    def _check_docker_available(self) -> bool:
        return shutil.which("docker") is not None
    
    def test_dockerfile(
        self,
        dockerfile_content: str,
        dockerfile_path: Optional[str] = None,
        build_context: Optional[str] = None,
        image_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.docker_available:
            return {
                "success": False,
                "error": "Docker CLI not available",
                "build_success": False,
                "test_success": False
            }
        
        syntax_result = self._validate_syntax(dockerfile_content)
        if not syntax_result["valid"]:
            return {
                "success": False,
                "error": "Dockerfile syntax validation failed",
                "syntax_errors": syntax_result.get("errors", []),
                "build_success": False,
                "test_success": False
            }
        
        temp_dockerfile = None
        cleanup_needed = False
        
        try:
            if dockerfile_path and os.path.exists(dockerfile_path):
                dockerfile_to_use = dockerfile_path
                if build_context is None:
                    build_context = os.path.dirname(dockerfile_path) or "."
            else:
                temp_dockerfile = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.Dockerfile', delete=False
                )
                temp_dockerfile.write(dockerfile_content)
                temp_dockerfile.close()
                dockerfile_to_use = temp_dockerfile.name
                cleanup_needed = True
                if build_context is None:
                    build_context = os.path.dirname(dockerfile_to_use) or "."
            
            if not image_name:
                image_name = f"dockerfile-test-{int(time.time())}"
            
            print(f"  Building Docker image '{image_name}'...", end="", flush=True)
            build_result = self._build_image(
                dockerfile_to_use,
                build_context,
                image_name
            )
            print(" Done" if build_result["success"] else " Failed")
            
            if build_result["success"]:
                print(f"\n  [Build Success] Time: {build_result.get('build_time', 0):.2f}s")
                build_output = build_result.get("output", "")
                if build_output:
                    output_lines = build_output.strip().split('\n')
                    if len(output_lines) > 5:
                        print(f"  [Build Output] Last 5 lines:")
                        for line in output_lines[-5:]:
                            if line.strip():
                                print(f"    {line[:100]}")
                    else:
                        print(f"  [Build Output] {build_output[:200]}")
            else:
                print(f"\n  [Build Failed] Time: {build_result.get('build_time', 0):.2f}s")
                build_errors = build_result.get("errors", "")
                if build_errors:
                    error_lines = build_errors.strip().split('\n')
                    print(f"  [Build Errors] Last 5 error lines:")
                    for line in error_lines[-5:]:
                        if line.strip():
                            print(f"    {line[:100]}")
            
            test_result = {"test_success": False}
            if build_result["success"]:
                print(f"  Testing Docker image...", end="", flush=True)
                test_result = self._test_image(image_name)
                print("Completed" if test_result["test_success"] else " Failed")
                
                if test_result["test_success"]:
                    test_output = test_result.get("output", "")
                    print(f"\n  [Test Success] Container started and executed successfully")
                    if test_output:
                        print(f"  [Test Output] {test_output.strip()[:200]}")
                else:
                    test_output = test_result.get("output", "")
                    print(f"\n  [Test Failed] Container test failed")
                    if test_output:
                        print(f"  [Test Error] {test_output.strip()[:200]}")
            
            return {
                "success": build_result["success"] and test_result.get("test_success", False),
                "build_success": build_result["success"],
                "build_time": build_result.get("build_time", 0),
                "build_output": build_result.get("output", ""),
                "build_errors": build_result.get("errors", ""),
                "test_success": test_result.get("test_success", False),
                "test_output": test_result.get("output", ""),
                "image_name": image_name,
                "syntax_valid": True
            }
        
        finally:
            if cleanup_needed and temp_dockerfile and os.path.exists(temp_dockerfile.name):
                try:
                    os.unlink(temp_dockerfile.name)
                except:
                    pass
    
    def _validate_syntax(self, dockerfile_content: str) -> Dict[str, Any]:
        if not dockerfile_content.strip():
            return {"valid": False, "errors": ["Dockerfile is empty"]}
        
        lines = dockerfile_content.split('\n')
        has_from = False
        errors = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                if stripped.upper().startswith("FROM"):
                    has_from = True
                    break
        
        if not has_from:
            errors.append("Dockerfile must start with a FROM instruction")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _build_image(
        self,
        dockerfile_path: str,
        build_context: str,
        image_name: str
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            print(f"\n  [Build Command] docker build -f {dockerfile_path} -t {image_name} {build_context}")
            
            result = subprocess.run(
                [
                    "docker", "build",
                    "-f", dockerfile_path,
                    "-t", image_name,
                    build_context
                ],
                capture_output=True,
                text=True,
                timeout=self.build_timeout,
                check=False
            )
            
            build_time = time.time() - start_time
            
            if result.returncode == 0:
                output_lines = result.stdout.split('\n')
                step_count = len([l for l in output_lines if 'Step' in l and '/' in l])
                final_size = None
                for line in reversed(output_lines):
                    if 'Successfully tagged' in line:
                        break
                    if 'MB' in line or 'GB' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part in ['MB', 'GB', 'KB'] and i > 0:
                                final_size = ' '.join(parts[max(0, i-1):i+1])
                                break
                        if final_size:
                            break
                
                return {
                    "success": True,
                    "build_time": round(build_time, 2),
                    "output": result.stdout,
                    "errors": "",
                    "step_count": step_count,
                    "final_size": final_size
                }
            else:
                return {
                    "success": False,
                    "build_time": round(build_time, 2),
                    "output": result.stdout,
                    "errors": result.stderr,
                    "returncode": result.returncode
                }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "build_time": self.build_timeout,
                "output": "",
                "errors": f"Build timed out after {self.build_timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "build_time": time.time() - start_time,
                "output": "",
                "errors": str(e)
            }
    
    def _test_image(self, image_name: str) -> Dict[str, Any]:
        try:
            test_command = ["docker", "run", "--rm", "--name", f"{image_name}-test", image_name, "echo", "test"]
            print(f"\n  [Test Command] {' '.join(test_command)}")
            
            result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode == 0:
                return {
                    "test_success": True,
                    "output": result.stdout,
                    "returncode": result.returncode
                }
            else:
                return {
                    "test_success": False,
                    "output": result.stderr or result.stdout,
                    "returncode": result.returncode
                }
        
        except subprocess.TimeoutExpired:
            return {
                "test_success": False,
                "output": "Container test timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "test_success": False,
                "output": str(e)
            }
    
    def cleanup_image(self, image_name: str) -> bool:
        if not self.docker_available:
            return False
        
        try:
            subprocess.run(
                ["docker", "rmi", "-f", image_name],
                capture_output=True,
                check=False
            )
            return True
        except:
            return False
    
    def print_test_report(self, test_results: Dict[str, Any]) -> None:
        print("\n" + "="*60)
        print("DOCKERFILE TEST REPORT")
        print("="*60)
        
        if not test_results.get("success"):
            print("\n[ERROR] Test failed")
            if test_results.get("error"):
                print(f"  Error: {test_results['error']}")
            if test_results.get("syntax_errors"):
                print(f"  Syntax Errors:")
                for err in test_results["syntax_errors"]:
                    print(f"    - {err}")
            if test_results.get("build_errors"):
                print(f"  Build Errors:")
                print(f"    {test_results['build_errors'][:500]}")
            print("\n" + "="*60 + "\n")
            return
        
        print(f"\nBUILD RESULTS:")
        print(f"  Status: {'SUCCESS' if test_results.get('build_success') else 'FAILED'}")
        if test_results.get("build_time"):
            print(f"  Build Time: {test_results.get('build_time', 0):.2f} seconds")
        
        print(f"\nTEST RESULTS:")
        print(f"  Status: {'SUCCESS' if test_results.get('test_success') else 'FAILED'}")
        
        if test_results.get("image_name"):
            print(f"  Image Name: {test_results['image_name']}")
        
        print("\n" + "="*60 + "\n")




