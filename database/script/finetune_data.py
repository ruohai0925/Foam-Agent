import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


def parse_case_content(case_content: str) -> Dict:
    """Parse a single case from the content."""
    case_data = {}
    
    # Extract index information
    index_match = re.search(r'<index>(.*?)</index>', case_content, re.DOTALL)
    if index_match:
        index_content = index_match.group(1)
        case_data['case_name'] = re.search(r'case name:\s*(.+)', index_content).group(1).strip()
        case_data['case_domain'] = re.search(r'case domain:\s*(.+)', index_content).group(1).strip()
        case_data['case_category'] = re.search(r'case category:\s*(.+)', index_content).group(1).strip()
        case_data['case_solver'] = re.search(r'case solver:\s*(.+)', index_content).group(1).strip()
    
    # Extract tutorials section
    tutorials_match = re.search(r'<tutorials>(.*?)</tutorials>', case_content, re.DOTALL)
    if tutorials_match:
        case_data['files'] = parse_tutorials(tutorials_match.group(1))
    
    return case_data


def parse_tutorials(tutorials_content: str) -> List[Dict]:
    """Parse the tutorials section to extract file information."""
    files = []
    
    # Find all directories
    dir_pattern = r'<directory_begin>directory name:\s*(.+?)\n(.*?)</directory_end>'
    for dir_match in re.finditer(dir_pattern, tutorials_content, re.DOTALL):
        folder_name = dir_match.group(1).strip()
        dir_content = dir_match.group(2)
        
        # Find all files in this directory
        file_pattern = r'<file_begin>file name:\s*(.+?)\n<file_content>(.*?)</file_content>'
        for file_match in re.finditer(file_pattern, dir_content, re.DOTALL):
            file_name = file_match.group(1).strip()
            file_content = file_match.group(2)
            
            files.append({
                'file_name': file_name,
                'folder_name': folder_name,
                'file_content': file_content
            })
    
    return files


def process_file(input_path: Path, output_path: Path, char_limit: int):
    """Process the OpenFOAM tutorials file and convert to JSONL format."""
    
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content by cases
    case_pattern = r'<case_begin>(.*?)</case_end>'
    cases = re.findall(case_pattern, content, re.DOTALL)
    
    skipped_files = []
    processed_records = []
    
    print(f"Found {len(cases)} cases to process")
    
    for i, case_content in enumerate(cases):
        if (i + 1) % 10 == 0:
            print(f"Processing case {i + 1}/{len(cases)}")
        
        case_data = parse_case_content(case_content)
        
        if 'files' not in case_data:
            continue
        
        for file_info in case_data['files']:
            # Check file content length
            if len(file_info['file_content']) > char_limit:
                full_path = f"{case_data['case_name']}/{file_info['folder_name']}/{file_info['file_name']}"
                print(f"\n⚠️  WARNING: Skipping file due to length > {char_limit} characters")
                print(f"   Path: {full_path}")
                print(f"   Length: {len(file_info['file_content'])} characters")
                print(f"   Content preview (first 500 chars):")
                print("   " + "-" * 60)
                print(file_info['file_content'][:500] + "...")
                print("   " + "-" * 60 + "\n")
                
                if full_path == "pitzDaily/system/blockMeshDict":
                    pass

                skipped_files.append({
                    'path': full_path,
                    'length': len(file_info['file_content'])
                })
                continue

            # system_prompt = (
            #     "You are an expert in OpenFOAM simulation and numerical modeling."
            #     f"Your task is to generate a complete and functional file named: <file_name>{file_info['file_name']}</file_name> within the <folder_name>{file_info['folder_name']}</folder_name> directory. "
            #     "Before finalizing the output, ensure:\n"
            #     "- Ensure units and dimensions are correct** for all physical variables.\n"
            #     f"- Ensure case solver settings are consistent with the user's requirements. Available solvers are: {case_data['case_solver']}.\n"
            #     "Provide only the code—no explanations, comments, or additional text."
            # )

            # user_prompt = (
            #     f"User requirement: {state['user_requirement']}\n"
            #     f"Just modify the necessary parts to make the file complete and functional."
            #     "Please ensure that the generated file is complete, functional, and logically sound."
            #     "Additionally, apply your domain expertise to verify that all numerical values are consistent with the user's requirements, maintaining accuracy and coherence."
            #     "When generating controlDict, do not include anything to preform post processing. Just include the necessary settings to run the simulation."
            # )
            
            record = {
                'file_name': file_info['file_name'],
                'folder_name': file_info['folder_name'],
                'case_name': case_data['case_name'],
                'case_domain': case_data['case_domain'],
                'case_category': case_data['case_category'],
                'case_solver': case_data['case_solver'],
                'file_content': file_info['file_content']

            }
            processed_records.append(record)
    
    # Write output
    print(f"\nWriting {len(processed_records)} records to {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in processed_records:
            json.dump(record, f, ensure_ascii=False)
            f.write('\n')
    
    # Summary
    print(f"\n📊 Processing Summary:")
    print(f"   Total cases processed: {len(cases)}")
    print(f"   Total files written: {len(processed_records)}")
    print(f"   Files skipped (too long): {len(skipped_files)}")
    
    if skipped_files:
        skipped_files = sorted(skipped_files, key=lambda x: x['length'])
        print(f"\n📋 Skipped files summary:")
        for skip in skipped_files[:10]:  # Show first 10
            print(f"   - {skip['path']} ({skip['length']} chars)")
        if len(skipped_files) > 10:
            print(f"   ... and {len(skipped_files) - 10} more")


def main():
    parser = argparse.ArgumentParser(description='Convert OpenFOAM tutorials to JSONL format for HuggingFace')
    parser.add_argument('--input', type=str,
                        default=str((Path(__file__).parent.parent / 'raw' / 'openfoam_tutorials_details.txt').resolve()),
                        help='Input file path (default: raw/openfoam_tutorials_details.txt)')
    parser.add_argument('--output', type=str,
                        default=str((Path(__file__).parent.parent / 'raw' / 'openfoam_finetune_data.jsonl').resolve()),
                        help='Output file path (default: raw/openfoam_finetune_data.jsonl)')
    parser.add_argument('--char-limit', type=int, default=2000,
                        help='Character limit for file content (default: 5000)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file '{input_path}' not found")
        return
    
    # Generate output filename if not specified
    if args.output is None:
        output_path = input_path.with_suffix('.jsonl')
    else:
        output_path = Path(args.output)
    
    print(f"📂 Input: {input_path}")
    print(f"💾 Output: {output_path}")
    print(f"📏 Character limit: {args.char_limit}")
    print()
    
    process_file(input_path, output_path, args.char_limit)
    
    print(f"\n✅ Done! Output saved to: {output_path}")
    print("\n💡 To load in HuggingFace datasets:")
    print("   from datasets import load_dataset")
    print(f"   dataset = load_dataset('json', data_files='{output_path}')")


if __name__ == "__main__":
    main()