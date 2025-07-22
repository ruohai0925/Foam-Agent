import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from collections import defaultdict
from dataclasses import dataclass

# Import LangChain components
from langchain.chat_models import init_chat_model
from langchain_community.chat_models import ChatAnthropic, ChatOllama
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel
import requests
import subprocess
import random
from botocore.exceptions import ClientError

from tqdm import tqdm
import itertools
import os
import json
import pathlib
from typing import Union, Dict
from contextlib import contextmanager
import boto3

# === Bedrock usage tracking code from tracking_aws.py ===
Usage = Dict[str, Union[int, float]]
default_usage_file = pathlib.Path("usage_nrel_aws.json")

# prices match https://aws.amazon.com/bedrock/pricing/ as of January 2025.
CLAUDE_3_5_HAIKU = 'arn:aws:bedrock:us-west-2:991404956194:application-inference-profile/g47vfd2xvs5w'
CLAUDE_3_5_SONNET = 'arn:aws:bedrock:us-west-2:991404956194:application-inference-profile/56i8iq1vib3e'
pricing = {
    CLAUDE_3_5_HAIKU: {'input': 0.0008, 'output': 0.004},
    CLAUDE_3_5_SONNET: {'input': 0.003, 'output': 0.015},
}

def track_usage(client: boto3.client, path: pathlib.Path = default_usage_file) -> boto3.client:
    old_invoke_model = client.invoke_model
    def tracked_invoke_model(*args, **kwargs):
        response = old_invoke_model(*args, **kwargs)
        old = read_usage(path)
        new, response_body = get_usage(response, model=kwargs.get('modelId', None))
        _write_usage(_merge_usage(old, new), path)
        return response_body
    client.invoke_model = tracked_invoke_model  # type:ignore
    return client

def get_usage(response, model=None) -> Usage:
    response_body = json.loads(response['body'].read().decode())
    usage = {'input_tokens': response_body['usage']['input_tokens'],
             'output_tokens': response_body['usage']['output_tokens']}
    try:
        costs = pricing[model]
    except KeyError:
        raise ValueError(f"Don't know prices for model {model} or {response.model}")
    cost = (usage.get('input_tokens', 0) * costs['input'] + usage.get('output_tokens', 0) * costs['output']) / 1_000
    usage['cost'] = cost
    return usage, response_body

def read_usage(path: pathlib.Path = default_usage_file) -> Usage:
    if os.path.exists(path):
        with open(path, "rt") as f:
            return json.load(f)
    else:
        return {}

def _write_usage(u: Usage, path: pathlib.Path):
    with open(path, "wt") as f:
        json.dump(u, f, indent=4)

def _merge_usage(u1: Usage, u2: Usage) -> Usage:
    return {k: u1.get(k, 0) + u2.get(k, 0) for k in itertools.chain(u1, u2)}

def new_default_client(default='boto3') -> boto3.client:
    global default_client
    default_client = track_usage(
        boto3.client('bedrock-runtime', region_name='us-west-2'))
    return default_client
# === End Bedrock usage tracking code ===


@dataclass
class Config:
    max_loop: int = 20
    batchsize: int = 10
    searchdocs: int = 2
    run_times: int = 1
    database_path: str = Path(__file__).resolve().parent.parent / "database"
    run_directory: str = Path(__file__).resolve().parent.parent / "runs"
    case_dir: str = ""
    max_time_limit: int = 36000
    model_provider: str = "openai"  # [openai, bedrock]
    model_version: str = "gpt-4o"
    temperature: float = 0.6


class ResponseWithThinkPydantic(BaseModel):
    think: str
    response: str


class LLMService:
    def __init__(self, config: Config):
        self.model_version = getattr(config, "model_version", "gpt-4o")
        self.temperature = getattr(config, "temperature", 0)
        self.model_provider = getattr(config, "model_provider", "openai")
        
        # Initialize statistics
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.failed_calls = 0
        self.retry_count = 0
        
        # Initialize the LLM
        if self.model_provider.lower() == "bedrock":
            bedrock_runtime = new_default_client()
            self.llm = ChatBedrockConverse(
                client=bedrock_runtime, 
                model_id=self.model_version, 
                temperature=self.temperature, 
                max_tokens=8192
            )
        elif self.model_provider.lower() == "openai":
            self.llm = init_chat_model(
                self.model_version, 
                model_provider=self.model_provider, 
                temperature=self.temperature
            )
        else:
            raise ValueError(f"{self.model_provider} is not a supported model_provider")
    
    def invoke(self, 
              user_prompt: str, 
              system_prompt: Optional[str] = None, 
              pydantic_obj: Optional[Type[BaseModel]] = None,
              max_retries: int = 10) -> Any:
        """
        Invoke the LLM with the given prompts and return the response.
        """
        self.total_calls += 1
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        # Calculate prompt tokens (simplified)
        prompt_tokens = sum(len(msg["content"].split()) for msg in messages)
        
        retry_count = 0
        while True:
            try:
                if pydantic_obj:
                    structured_llm = self.llm.with_structured_output(pydantic_obj)
                    response = structured_llm.invoke(messages)
                else:
                    if self.model_version.startswith("deepseek"):
                        structured_llm = self.llm.with_structured_output(ResponseWithThinkPydantic)
                        response = structured_llm.invoke(messages)
                        response = response.response
                    else:
                        response = self.llm.invoke(messages)
                        response = response.content

                # Calculate completion tokens (simplified)
                response_content = str(response)
                completion_tokens = len(response_content.split())
                total_tokens = prompt_tokens + completion_tokens
                
                # Update statistics
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens += total_tokens
                
                return response
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'Throttling' or e.response['Error']['Code'] == 'TooManyRequestsException':
                    retry_count += 1
                    self.retry_count += 1
                    
                    if retry_count > max_retries:
                        self.failed_calls += 1
                        raise Exception(f"Maximum retries ({max_retries}) exceeded: {str(e)}")
                    
                    base_delay = 1.0
                    max_delay = 60.0
                    delay = min(max_delay, base_delay * (2 ** (retry_count - 1)))
                    jitter = random.uniform(0, 0.1 * delay)
                    sleep_time = delay + jitter
                    
                    print(f"ThrottlingException occurred: {str(e)}. Retrying in {sleep_time:.2f} seconds (attempt {retry_count}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    self.failed_calls += 1
                    raise e
            except Exception as e:
                self.failed_calls += 1
                raise e

    def get_stats(self):
        """Get usage statistics"""
        return {
            'total_calls': self.total_calls,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_tokens,
            'failed_calls': self.failed_calls,
            'retry_count': self.retry_count
        }


def load_jsonl_data(file_path: Path) -> List[Dict]:
    """Load data from JSONL file"""
    print(f"Loading jsonl data from {file_path}")
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def group_by_case_name(data: List[Dict]) -> Dict[str, List[Dict]]:
    """Group records by case_name"""
    grouped = defaultdict(list)
    for record in data:
        case_name = record.get('case_name', 'unknown')
        grouped[case_name].append(record)
    return dict(grouped)


def create_system_prompt() -> str:
    """Create the system prompt for generating user requirements"""
    return """You are an expert OpenFOAM simulation engineer. Your task is to analyze OpenFOAM case files and generate a realistic user requirement that a simulation engineer would specify when requesting such a simulation.

Based on the provided OpenFOAM case files, generate a user_requirement that follows these patterns:

STRUCTURE REQUIREMENTS:
1. Start with "do a [simulation type]" or "Perform a [simulation type]" or "Conduct a [simulation type]"
2. Include solver specification: "using [solver name] solver" or "Use [solver name] solver"
3. Specify geometric details with precise dimensions
4. Define all boundary conditions for different patches/surfaces
5. Include time parameters (start time, end time, timestep, output frequency)
6. Specify physical properties (viscosity, density, temperature, pressure, etc.)
7. Mention grid/mesh details when relevant
8. Include algorithm details (PIMPLE, SIMPLE, etc.) when applicable

TECHNICAL ACCURACY:
- Use correct OpenFOAM terminology and solver names
- Include realistic engineering values with proper units
- Specify boundary condition types accurately (fixedValue, zeroGradient, noSlip, etc.)
- Include material properties relevant to the simulation type
- Mention turbulence models when applicable (k-epsilon, RAS, etc.)

FORMAT REQUIREMENTS:
- Generate a single, comprehensive sentence or paragraph
- Use technical language appropriate for CFD engineers
- Include specific numerical values extracted from the case files
- Maintain consistency with OpenFOAM naming conventions

EXAMPLES OF GOOD PATTERNS:
- "do a Reynolds-Averaged Simulation (RAS) pitzdaily simulation. Use PIMPLE algorithm. The domain is a 2D millimeter-scale channel geometry. Boundary conditions specify a fixed velocity of 10m/s at the inlet (left), zero gradient pressure at the outlet (right), and no-slip conditions for walls. Use timestep of 0.0001 and output every 0.01. Finaltime is 0.3. use nu value of 1e-5."

- "do an incompressible lid driven cavity flow. The cavity is a square with dimensions normalized to 1 unit on both the x and y axes and very thin in the z-direction (0.1 unit scaled down by a factor of 0.1, making it effectively 2D). Use a grid of 20X20 in x and y direction and 1 cell in z-direction(due to the expected 2D flow characteristics). The top wall ('movingWall') moves in the x-direction with a uniform velocity of 1 m/s. The 'fixedWalls' have a no-slip boundary condition (velocity equal to zero at the wall). The front and back faces are designated as 'empty'. The simulation runs from time 0 to 10 with a time step of 0.005 units, and results are output every 100 time steps. The viscosity (nu) is set as constant with a value of 1e-05 m^2/s."

Generate ONLY the user_requirement text as a single comprehensive statement, with no additional explanation, formatting, or metadata."""


def create_user_prompt(case_data: List[Dict]) -> str:
    """Create the user prompt with case file information"""
    case_info = case_data[0]  # Get case metadata from first record
    
    prompt = f"""Analyze this OpenFOAM case and generate a realistic user requirement:

CASE METADATA:
- Case Name: {case_info['case_name']}
- Domain: {case_info['case_domain']}
- Category: {case_info['case_category']}
- Solver: {case_info['case_solver']}

CASE FILES ANALYSIS:
"""
    
    # Group files by folder for better organization
    files_by_folder = defaultdict(list)
    for record in case_data:
        files_by_folder[record['folder_name']].append(record)
    
    # Add file contents organized by folder
    for folder_name, files in files_by_folder.items():
        prompt += f"\n=== {folder_name}/ ===\n"
        for record in files:
            file_name = record['file_name']
            file_content = record['file_content']
            prompt += f"\n--- {file_name} ---\n{file_content}\n"
    
    prompt += """

TASK:
Based on the case files above, extract the key simulation parameters and generate a realistic user_requirement that an engineer would specify when requesting this simulation. Focus on:

1. Simulation type and solver
2. Domain geometry and dimensions
3. Boundary conditions for all patches
4. Time settings (timestep, end time, output frequency)
5. Physical properties (viscosity, density, temperature, etc.)
6. Grid/mesh specifications
7. Algorithm settings (PIMPLE, SIMPLE, turbulence models, etc.)

Generate a single, comprehensive user_requirement statement that captures all essential simulation parameters."""
    
    return prompt


def process_cases(grouped_data: Dict[str, List[Dict]], llm_service: LLMService, output_path: Path):
    """Process each case and generate user requirements"""
    results = []
    total_cases = len(grouped_data)
    
    print(f"Processing {total_cases} cases...")
    
    for i, (case_name, case_data) in tqdm(enumerate(grouped_data.items(), 1)):
        print(f"Processing case {i}/{total_cases}: {case_name}")
        
        try:
            # Create prompts
            system_prompt = create_system_prompt()
            user_prompt = create_user_prompt(case_data)
            
            # Invoke LLM
            user_requirement = llm_service.invoke(
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )
            
            # Create result record
            case_info = case_data[0]  # Get metadata from first record
            result = {
                'case_name': case_name,
                'case_domain': case_info['case_domain'],
                'case_category': case_info['case_category'],
                'case_solver': case_info['case_solver'],
                'user_requirement': str(user_requirement).strip(),
                'file_count': len(case_data),
                'files': [{'folder_name': r['folder_name'], 'file_name': r['file_name']} for r in case_data]
            }
            
            results.append(result)
            
            # Save progress after each case
            with open(output_path, 'w', encoding='utf-8') as f:
                for result_record in results:
                    json.dump(result_record, f, ensure_ascii=False)
                    f.write('\n')
            
            print(f"  ✓ Generated user requirement for {case_name}")
            print(f"  Preview: ========================================\n {str(user_requirement)}\n\n\n")
            
        except Exception as e:
            print(f"  ❌ Error processing {case_name}: {str(e)}")
            continue
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Generate user requirements from OpenFOAM cases')
    parser.add_argument('--input', type=str,
                        default='raw/openfoam_finetune_data.jsonl',
                        help='Input JSONL file path')
    parser.add_argument('--output', type=str,
                        default='raw/openfoam_user_requirements.jsonl',
                        help='Output JSONL file path')
    parser.add_argument('--model-provider', type=str, default='bedrock',
                        choices=['openai', 'bedrock'],
                        help='Model provider')
    parser.add_argument('--model-version', type=str, default='arn:aws:bedrock:us-west-2:991404956194:application-inference-profile/56i8iq1vib3e',
                        help='Model version')
    parser.add_argument('--temperature', type=float, default=0.6,
                        help='Temperature for LLM')
    
    args = parser.parse_args()
    
    # Setup paths
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"❌ Error: Input file '{input_path}' not found")
        return
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"📂 Input: {input_path}")
    print(f"💾 Output: {output_path}")
    print(f"🤖 Model: {args.model_provider}/{args.model_version}")
    print(f"🌡️  Temperature: {args.temperature}")
    print()
    
    # Initialize config and LLM service
    config = Config(
        model_provider=args.model_provider,
        model_version=args.model_version,
        temperature=args.temperature
    )
    
    print("Initializing LLM service...")
    llm_service = LLMService(config)
    
    # Load and process data
    print("Loading data...")
    data = load_jsonl_data(input_path)
    print(f"Loaded {len(data)} records")
    
    print("Grouping by case name...")
    grouped_data = group_by_case_name(data)
    print(f"Found {len(grouped_data)} unique cases")
    
    # Process cases
    results = process_cases(grouped_data, llm_service, output_path)
    
    # Print statistics
    stats = llm_service.get_stats()
    print(f"\n📊 Processing Summary:")
    print(f"   Total cases processed: {len(results)}")
    print(f"   LLM calls made: {stats['total_calls']}")
    print(f"   Failed calls: {stats['failed_calls']}")
    print(f"   Total tokens used: {stats['total_tokens']}")
    print(f"   Prompt tokens: {stats['total_prompt_tokens']}")
    print(f"   Completion tokens: {stats['total_completion_tokens']}")
    
    print(f"\n✅ Done! User requirements saved to: {output_path}")
    print("\n💡 To load the results:")
    print("   import json")
    print("   with open('{}', 'r') as f:".format(output_path))
    print("       for line in f:")
    print("           data = json.loads(line)")
    print("           print(data['case_name'], ':', data['user_requirement'])")


if __name__ == "__main__":
    main()