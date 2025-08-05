import os
import subprocess
import argparse
import concurrent.futures
from pathlib import Path
import re
import json

def read_files_into_dict(base_path, stats=None):
    """
    读取指定目录下的文件内容并存储到字典中
    
    该函数会：
    1. 读取Allrun脚本文件（如果存在）
    2. 遍历base_path下一级子目录中的所有文件
    3. 统计文件读取的成功/失败情况
    4. 返回文件内容、文件名、文件夹名和统计信息
    
    参数:
        base_path (str): 要扫描的基础目录路径
        stats (dict): 统计信息字典，如果为None则创建新的
    
    返回:
        tuple: (allrun_content, file_contents, file_names, folder_names, stats)
    """
    if stats is None:
        stats = {
            "files_total_scanned": 0,      # 总共扫描的文件数
            "files_skipped_encoding": 0,   # 因编码问题跳过的文件数
            "files_skipped_large": 0,      # 因文件过大跳过的文件数
            "files_read_success": 0,       # 成功读取的文件数
            "allrun_read_success": 0,      # 成功读取的Allrun文件数
            "allrun_read_fail": 0          # 读取失败的Allrun文件数
        }

    file_contents, file_names, folder_names = {}, [], {}
    base_depth = base_path.rstrip(os.sep).count(os.sep)  # 计算基础目录的深度
    
    print(f"🔍 开始扫描目录: {base_path}")
    print(f"📊 基础目录深度: {base_depth}")

    # 读取'Allrun'文件
    allrun_path = os.path.join(base_path, "Allrun")
    allrun_content = "None"
    
    # 检查"Allrun"文件是否存在并尝试读取
    if os.path.isfile(allrun_path):
        stats["files_total_scanned"] += 1  # 统计扫描的Allrun文件
        
        try:
            with open(allrun_path, "r") as file_handle:
                allrun_content = file_handle.read()
            stats["allrun_read_success"] += 1
            print(f"✅ 成功读取Allrun文件: {allrun_path}")
        except UnicodeDecodeError:
            print(f"❌ 因编码错误跳过文件: {allrun_path}")
            stats["files_skipped_encoding"] += 1
            stats["allrun_read_fail"] += 1
        except Exception as e:
            print(f"❌ 读取文件出错 {allrun_path}: {e}")
            stats["allrun_read_fail"] += 1
    else:
        print(f"⚠️  Allrun文件不存在: {allrun_path}")

    # 遍历base_path目录读取文件
    for root, _, files in os.walk(base_path):
        # 只读取base_path下一级的文件
        if root.rstrip(os.sep).count(os.sep) == base_depth + 1:
            print(f"📁 扫描子目录: {root}")
            for file in files:
                file_path = os.path.join(root, file)
                
                stats["files_total_scanned"] += 1  # 统计扫描的文件
                
                try:
                    with open(file_path, "r") as file_handle:
                        lines = file_handle.readlines()

                        file_contents[file] = "".join(lines)
                        stats["files_read_success"] += 1

                        folder_names[file] = os.path.relpath(root, base_path)
                        file_names.append(file)
                        print(f"  ✅ 成功读取: {file}")
                except UnicodeDecodeError:
                    print(f"  ❌ 因编码错误跳过: {file_path}")
                    stats["files_skipped_encoding"] += 1
                except Exception as e:
                    print(f"  ❌ 读取文件出错 {file_path}: {e}")
    
    print(f"📈 文件读取统计: {stats}")
    return allrun_content, file_contents, file_names, folder_names, stats


def find_cases(root_dir):
    """
    遍历root_dir目录树，查找包含'system'文件夹的案例
    
    该函数会：
    1. 递归遍历目录树
    2. 识别包含system文件夹的OpenFOAM案例
    3. 提取案例元数据（案例名、求解器、类别、领域）
    4. 收集漏斗式统计信息
    
    参数:
        root_dir (str): 要搜索的根目录路径
    
    返回:
        tuple: (cases, stats) - 案例列表和统计信息
    """
    cases = []
    
    # 初始化统计字典
    stats = {
        "directories_scanned": 0,      # 扫描的目录数
        "directories_with_system": 0,  # 包含system文件夹的目录数
        "files_total_scanned": 0,      # 总共扫描的文件数
        "files_skipped_encoding": 0,   # 因编码问题跳过的文件数
        "files_skipped_large": 0,      # 因文件过大跳过的文件数
        "files_read_success": 0,       # 成功读取的文件数
        "allrun_read_success": 0,      # 成功读取的Allrun文件数
        "allrun_read_fail": 0          # 读取失败的Allrun文件数
    }

    # Get FOAM_TUTORIALS from environment or fallback
    FOAM_TUTORIALS = os.environ.get("FOAM_TUTORIALS", "/home/somasn/Documents/LLM/OpenFOAM-10/tutorials")
    blockmesh_resource_dir = os.path.join(FOAM_TUTORIALS, "resources", "blockMesh")

    for root, dirs, files in os.walk(root_dir):
        stats["directories_scanned"] += 1  # Scanning this directory
    print(f"🚀 开始搜索OpenFOAM案例，根目录: {root_dir}")


    for root, dirs, files in os.walk(root_dir):
        stats["directories_scanned"] += 1  # 统计扫描的目录

        # 检查当前目录是否包含'system'文件夹
        if "system" in dirs:
            stats["directories_with_system"] += 1
            print(f"🎯 发现OpenFOAM案例: {root}")

            # 读取当前目录（root）中的文件
            allrun_content, file_contents, file_names, folder_names, file_stats = read_files_into_dict(root, stats={
                "files_total_scanned": 0,
                "files_skipped_encoding": 0,
                "files_skipped_large": 0,
                "files_read_success": 0,
                "allrun_read_success": 0,
                "allrun_read_fail": 0
            })
            
            # 将file_stats合并到全局stats中
            stats["files_total_scanned"] += file_stats["files_total_scanned"]
            stats["files_skipped_encoding"] += file_stats["files_skipped_encoding"]
            stats["files_skipped_large"] += file_stats["files_skipped_large"]
            stats["files_read_success"] += file_stats["files_read_success"]
            stats["allrun_read_success"] += file_stats["allrun_read_success"]
            stats["allrun_read_fail"] += file_stats["allrun_read_fail"]

            # 案例名称是当前目录的名称
            case_name = os.path.basename(root)
            
            # 初始化求解器、类别和领域
            solver, category, domain = None, None, None
            
            # 向上移动到父目录，最多搜索3层
            current_path = os.path.dirname(root)
            found_foam = False

            print(f"🔍 分析案例路径结构: {case_name}")
            print(f"  当前路径: {current_path}")

            for level in range(3):
                # 如果路径为空或已到达root_dir，则停止
                if (not current_path) or (os.path.basename(current_path) == os.path.basename(root_dir)):
                    break
                
                dir_name = os.path.basename(current_path)
                print(f"  第{level+1}层目录: {dir_name}")
                
                # 如果目录名以'Foam'结尾，将其视为求解器
                if dir_name.endswith("Foam"):
                    solver = dir_name
                    # 求解器目录的父目录被视为领域
                    domain = os.path.basename(os.path.dirname(current_path))
                    found_foam = True
                    print(f"  🎯 找到求解器: {solver}, 领域: {domain}")
                    break
                elif level == 0:
                    category = dir_name
                    print(f"  📂 设置类别: {category}")
                
                # 向上移动一层
                current_path = os.path.dirname(current_path)
            
            # 如果没有找到以'Foam'结尾的求解器目录，使用相对路径逻辑
            if not found_foam:
                category = None  # 重置类别，以防上面部分设置
                relative_path = os.path.relpath(root, root_dir)
                path_components = relative_path.split(os.sep)
                
                print(f"  🔄 使用相对路径逻辑: {relative_path}")
                print(f"    路径组件: {path_components}")
                
                # 如果相对路径正好有3个组件: domain/solver/caseName
                if len(path_components) == 3:
                    domain, solver = path_components[0], path_components[1]
                    print(f"  📋 3组件路径: domain={domain}, solver={solver}")
                # 如果相对路径正好有4个组件: domain/solver/category/caseName
                elif len(path_components) == 4:
                    domain, solver, category = path_components[0], path_components[1], path_components[2]
                    print(f"  📋 4组件路径: domain={domain}, solver={solver}, category={category}")
            
            print(f"  📊 最终元数据: case_name={case_name}, solver={solver}, category={category}, domain={domain}")

            # --- NEW LOGIC: Check for missing blockMeshDict and copy if referenced in Allrun ---
            system_dir = os.path.join(root, "system")
            blockmeshdict_path = os.path.join(system_dir, "blockMeshDict")
            if not os.path.isfile(blockmeshdict_path):
                # Only try if Allrun exists and was read
                if allrun_content != "None":
                    # Look for blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/<name>
                    pattern = r"blockMesh\s+-dict\s+\$FOAM_TUTORIALS/resources/blockMesh/([\w\d_]+)"
                    match = re.search(pattern, allrun_content)
                    if match:
                        referenced_file = match.group(1)
                        src_blockmeshdict = os.path.join(blockmesh_resource_dir, referenced_file)
                        if os.path.isfile(src_blockmeshdict):
                            # Copy to system/blockMeshDict
                            try:
                                with open(src_blockmeshdict, "r") as src_f:
                                    blockmesh_content = src_f.read()
                                # Save to the case's system dir
                                os.makedirs(system_dir, exist_ok=True)
                                with open(blockmeshdict_path, "w") as dst_f:
                                    dst_f.write(blockmesh_content)
                                # Add to in-memory structures for output
                                file_contents["blockMeshDict"] = blockmesh_content
                                file_names.append("blockMeshDict")
                                folder_names["blockMeshDict"] = "system"
                                print(f"[INFO] Copied {src_blockmeshdict} to {blockmeshdict_path} for case {case_name}")
                            except Exception as e:
                                print(f"[WARNING] Failed to copy {src_blockmeshdict} to {blockmeshdict_path}: {e}")
                        else:
                            print(f"[WARNING] Referenced blockMeshDict {src_blockmeshdict} not found for case {case_name}")
                    else:
                        print(f"[INFO] No blockMesh -dict reference found in Allrun for case {case_name}")
                else:
                    print(f"[INFO] No Allrun file to check for blockMeshDict reference in case {case_name}")
            # --- END NEW LOGIC ---

            # Append the extracted metadata to the 'cases' list
            
            # 将提取的元数据添加到'cases'列表

            cases.append({
                "case_name": case_name,
                "solver": solver,
                "category": category,
                "domain": domain,
                "folder_names": folder_names,
                "file_names": file_names,
                "file_contents": file_contents,
                "allrun": allrun_content
            })
    
    print(f"🎉 案例搜索完成！找到 {len(cases)} 个案例")
    print(f"📈 最终统计: {stats}")
    return cases, stats



def save_cases_to_file(cases, output_dir):
    """
    将案例详情、摘要或Allrun内容保存到文件
    
    该函数会生成4个文件：
    1. openfoam_allrun_scripts.txt - 包含Allrun脚本的文件
    2. openfoam_tutorials_structure.txt - 教程结构摘要
    3. openfoam_tutorials_details.txt - 详细的教程内容
    4. openfoam_case_stats.json - 案例统计信息
    
    参数:
        cases (list): 案例列表
        output_dir (str): 输出目录路径
    """
    
    allrun_filepath = f"{output_dir}/openfoam_allrun_scripts.txt"
    tutorials_summary_filepath = f"{output_dir}/openfoam_tutorials_structure.txt"
    tutorial_filepath = f"{output_dir}/openfoam_tutorials_details.txt"
    case_stats_filepath = f"{output_dir}/openfoam_case_stats.json"
    
    allrun_text = ''
    tutorials_summary_text = ''
    tutorials_text = ''
    
    # 初始化案例统计字典 - 使用集合(set)实现自动去重
    # 集合的特性：不允许重复元素，自动去除重复值
    case_stats = {
        'case_name': set(),      # 存储所有案例的名称，自动去重
        'case_domain': set(),    # 存储所有案例的领域，自动去重
        'case_category': set(),  # 存储所有案例的类别，自动去重  
        'case_solver': set()     # 存储所有案例的求解器，自动去重
    }
    
    print(f"💾 开始保存案例数据到目录: {output_dir}")
    print(f"📝 处理 {len(cases)} 个案例...")
    
    for i, case in enumerate(cases):
        case_name, case_domain, case_category, case_solver = (
            case["case_name"], case["domain"], case["category"], case["solver"]
        )
        
        print(f"  📋 处理案例 {i+1}/{len(cases)}: {case_name}")
        
        # 使用集合的add()方法添加元素，自动去重
        # 如果元素已存在，add()不会重复添加
        if case_name:
            case_stats['case_name'].add(case_name)
            print(f"    🏷️  添加案例名称: {case_name} (当前案例名称总数: {len(case_stats['case_name'])})")
        if case_domain:
            case_stats['case_domain'].add(case_domain)
            print(f"    🏷️  添加领域: {case_domain} (当前领域总数: {len(case_stats['case_domain'])})")
        if case_category:
            case_stats['case_category'].add(case_category)
            print(f"    🏷️  添加类别: {case_category} (当前类别总数: {len(case_stats['case_category'])})")
        if case_solver:
            case_stats['case_solver'].add(case_solver)
            print(f"    🏷️  添加求解器: {case_solver} (当前求解器总数: {len(case_stats['case_solver'])})")
        
        # 保存案例索引
        case_index_text = "<index>\n"
        case_index_text += f"case name: {case_name}\n"
        case_index_text += f"case domain: {case_domain}\n"
        case_index_text += f"case category: {case_category}\n"
        case_index_text += f"case solver: {case_solver}\n"
        case_index_text += "</index>\n\n"
        
        # 保存目录结构
        folder_file_dict = {}
        for file_name, folder_name in case["folder_names"].items():
            if folder_name not in folder_file_dict:
                folder_file_dict[folder_name] = []
            folder_file_dict[folder_name].append(file_name)
        
        dir_structure_text = "<directory_structure>\n"
        for folder_name, file_names in folder_file_dict.items():
            dir_structure_text += f"<dir>directory name: {folder_name}. "
            dir_structure_text += f"File names in this directory: [{', '.join(file_names)}]</dir>\n"
        dir_structure_text += "</directory_structure>\n\n"
        
        print(f"    📁 目录结构: {list(folder_file_dict.keys())}")
        print(f"    📄 文件数量: {len(case['file_names'])}")
        
        if case["allrun"] != "None":
            # 保存Allrun内容
            allrun_text += f'''
<case_begin>
{case_index_text}
{dir_structure_text}
<allrun_script>
{case["allrun"]}
</allrun_script>
</case_end>\n\n\n
'''
            print(f"    ✅ 包含Allrun脚本")

        # 保存教程摘要
        tutorials_summary_text += f"<case_begin>\n{case_index_text}\n{dir_structure_text}\n</case_end>\n\n"

        # 保存详细教程
        tutorials_text += f"<case_begin>\n{case_index_text}\n{dir_structure_text}\n<tutorials>\n"
        
        print(f"    📝 开始处理详细教程内容...")
        print(f"    📁 需要处理的目录数量: {len(folder_file_dict)}")
        
        for folder_name, file_names in folder_file_dict.items():
            print(f"      📂 处理目录: {folder_name}")
            print(f"        📄 该目录下的文件数量: {len(file_names)}")
            print(f"        📋 文件列表: {file_names}")
            
            tutorials_text += f"<directory_begin>directory name: {folder_name}\n"
            for i, file_name in enumerate(file_names):
                print(f"          📄 处理文件 {i+1}/{len(file_names)}: {file_name}")
                
                tutorials_text += f"<file_begin>file name: {file_name}\n"
                
                # 删除注释，如许可证信息
                original_content = case['file_contents'][file_name]
                print(f"            📊 原始文件大小: {len(original_content)} 字符")
                
                # 删除 /* */ 类型的注释
                cleaned_text = re.sub(r'/\*.*?\*/', '', original_content, flags=re.DOTALL)
                print(f"            🧹 删除 /* */ 注释后大小: {len(cleaned_text)} 字符")
                
                # 删除 // 类型的注释
                cleaned_text = re.sub(r'//.*', '', cleaned_text)
                print(f"            🧹 删除 // 注释后大小: {len(cleaned_text)} 字符")
                
                # 计算清理效果
                reduction = len(original_content) - len(cleaned_text)
                if reduction > 0:
                    print(f"            📉 清理效果: 删除了 {reduction} 字符 ({reduction/len(original_content)*100:.1f}%)")
                else:
                    print(f"            ✅ 文件无需清理")

                tutorials_text += f"<file_content>{cleaned_text}</file_content>\n"
                tutorials_text += f"</file_end>\n\n"
            
            tutorials_text += f"</directory_end>\n\n"
            print(f"      ✅ 目录 {folder_name} 处理完成")

        tutorials_text += "</tutorials>\n</case_end>\n\n\n"
        print(f"    ✅ 案例 {case_name} 的详细教程内容处理完成")

    # 保存文件
    print(f"💾 保存Allrun脚本文件: {allrun_filepath}")
    with open(allrun_filepath, "w", encoding="utf-8") as file:
        file.write(allrun_text)
    
    print(f"💾 保存教程结构文件: {tutorials_summary_filepath}")
    with open(tutorials_summary_filepath, "w", encoding="utf-8") as file:
        file.write(tutorials_summary_text)
            
    print(f"💾 保存详细教程文件: {tutorial_filepath}")
    with open(tutorial_filepath, "w", encoding="utf-8") as file:
        file.write(tutorials_text)
    
    # 处理统计信息 - 将集合转换为列表以便JSON序列化
    # 添加"None"作为默认类别选项
    case_stats['case_category'].add("None")
    
    # 将集合转换为列表，保持去重后的唯一值
    # 这样既享受了集合的去重功能，又满足了JSON序列化的要求
    case_stats['case_name'] = list(case_stats['case_name'])
    case_stats['case_category'] = list(case_stats['case_category'])
    case_stats['case_domain'] = list(case_stats['case_domain'])
    case_stats['case_solver'] = list(case_stats['case_solver'])
    
    print(f"💾 保存案例统计文件: {case_stats_filepath}")
    print(f"📊 最终统计信息 (已去重):")
    print(f"    🏷️  案例名称数量: {len(case_stats['case_name'])} - {case_stats['case_name']}")
    print(f"    🏷️  领域数量: {len(case_stats['case_domain'])} - {case_stats['case_domain']}")
    print(f"    🏷️  类别数量: {len(case_stats['case_category'])} - {case_stats['case_category']}")
    print(f"    🏷️  求解器数量: {len(case_stats['case_solver'])} - {case_stats['case_solver']}")
    
    with open(case_stats_filepath, "w", encoding="utf-8") as file:
        json.dump(case_stats, file, ensure_ascii=False, indent=4)
            

def get_commands_from_directory(directory_path):
    """
    从指定目录检索所有命令文件名
    
    参数:
        directory_path (str): 要扫描的目录路径
    
    返回:
        list: 命令文件名列表
    
    异常:
        FileNotFoundError: 如果目录不存在
    """
    if not os.path.exists(directory_path):
        raise FileNotFoundError(f"目录 {directory_path} 不存在。")
    return [entry.name for entry in os.scandir(directory_path) if entry.is_file()]

def get_command_help(command, directory_path):
    """
    获取指定命令的帮助信息
    
    这个函数就像在命令行中运行 "命令名 -help" 一样
    例如：blockMesh -help, interFoam -help, simpleFoam -help
    
    参数:
        command (str): 命令名（可执行文件名）
        directory_path (str): 命令所在目录
    
    返回:
        str: 命令的帮助信息（相当于Windows中运行 "程序名 /?" 的输出）
    """
    try:
        # 构建完整的命令路径
        command_path = os.path.join(directory_path, command)
        
        # 设置OpenFOAM环境变量，确保动态库能被正确加载
        # 这相当于在运行命令前先执行 "source /opt/openfoam10/etc/bashrc"
        env = os.environ.copy()
        
        # 获取OpenFOAM安装目录（从directory_path推断）
        # 例如：/opt/openfoam10/platforms/linux64GccDPInt32Opt/bin -> /opt/openfoam10
        wm_project_dir = str(Path(directory_path).parent.parent.parent)
        
        # 设置关键的OpenFOAM环境变量
        env['WM_PROJECT_DIR'] = wm_project_dir
        env['FOAM_LIBBIN'] = f"{wm_project_dir}/platforms/linux64GccDPInt32Opt/lib"
        env['LD_LIBRARY_PATH'] = f"{wm_project_dir}/platforms/linux64GccDPInt32Opt/lib:{env.get('LD_LIBRARY_PATH', '')}"
        
        print(f"    🔧 设置环境变量: WM_PROJECT_DIR={wm_project_dir}")
        
        # 运行命令并获取帮助信息
        # 这就像在Windows中运行 "C:\Program Files\App\program.exe /?"
        result = subprocess.run(
            f"{command_path} -help", 
            shell=True, 
            capture_output=True, 
            text=True,
            env=env  # 使用设置好的环境变量
        )
        
        # 如果命令成功执行，返回标准输出；否则返回错误信息
        if result.returncode == 0:
            print(f"    ✅ 成功获取 {command} 的帮助信息")
            return result.stdout
        else:
            print(f"    ❌ 获取 {command} 帮助信息失败: {result.stderr[:100]}...")
            return result.stderr
            
    except Exception as e:
        print(f"    ❌ 执行 {command} 时出错: {str(e)}")
        return str(e)

def fetch_command_helps(commands, directory_path, wm_project_dir=None):
    """
    并行获取多个命令的帮助信息
    
    参数:
        commands (list): 命令列表
        directory_path (str): 命令所在目录
        wm_project_dir (str): OpenFOAM安装目录，用于设置环境变量
    
    返回:
        dict: 命令名到帮助信息的映射
    """
    print(f"🔍 开始获取 {len(commands)} 个命令的帮助信息...")
    
    # 如果提供了wm_project_dir，传递给get_command_help函数
    if wm_project_dir:
        print(f"🔧 使用OpenFOAM路径: {wm_project_dir}")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 为每个命令创建一个包装函数，传递wm_project_dir
        def get_help_with_env(cmd):
            return get_command_help(cmd, directory_path)
        
        return dict(zip(commands, executor.map(get_help_with_env, commands)))

if __name__ == "__main__":
    # 使用示例：
    # python ./database/script/tutorial_parser.py --output_dir=./database/raw --wm_project_dir=$WM_PROJECT_DIR
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--wm_project_dir", required=True, help="WM_PROJECT_DIR路径")
    parser.add_argument("--output_dir", default='./database', help="保存输出文件的目录")
    args = parser.parse_args()
    
    print(f"🚀 开始解析OpenFOAM教程...")
    print(f"📂 WM_PROJECT_DIR: {args.wm_project_dir}")
    print(f"📂 输出目录: {args.output_dir}")

    tutorial_path = os.path.join(args.wm_project_dir, "tutorials")
    print(f"📚 教程路径: {tutorial_path}")
    
    cases_info, case_stats = find_cases(tutorial_path)
    print(f"📈 最终统计: {case_stats}")
    print(f"🎯 在 {tutorial_path} 中找到 {len(cases_info)} 个案例")
    

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 创建输出目录: {output_dir}")

    save_cases_to_file(cases_info, output_dir)

    # 处理OpenFOAM命令
    # 检查默认路径是否存在
    commands_path = Path(args.wm_project_dir) / "platforms/linux64GccDPInt32Opt/bin"

    if not commands_path.exists():
        print(f"⚠️  默认命令路径不存在: {commands_path}")
        
        # 尝试查找其他可能的路径
        platforms_dir = Path(args.wm_project_dir) / "platforms"
        if platforms_dir.exists():
            # 查找所有平台目录
            platform_dirs = [d for d in platforms_dir.iterdir() if d.is_dir()]
            print(f"🔍 找到的平台目录: {[d.name for d in platform_dirs]}")
            
            # 选择第一个包含bin目录的平台
            for platform_dir in platform_dirs:
                bin_path = platform_dir / "bin"
                if bin_path.exists():
                    commands_path = bin_path
                    print(f"✅ 使用备选路径: {commands_path}")
                    break
        else:
            print(f"❌ 找不到platforms目录: {platforms_dir}")

    print(f"🔧 扫描命令目录: {commands_path}")
    
    # 获取所有OpenFOAM命令文件
    # 这些命令文件就像Windows的.exe文件，是Linux下的可执行文件
    # 例如：blockMesh, decomposePar, interFoam, simpleFoam 等
    # 它们都是编译好的二进制可执行文件，可以直接在命令行中运行
    commands = get_commands_from_directory(commands_path)
    print(f"📋 找到 {len(commands)} 个OpenFOAM命令（可执行文件）")
    
    # 显示前几个命令作为示例
    if commands:
        print(f"🔍 命令示例: {commands[:5]}...")  # 显示前5个命令
        print(f"💡 这些命令就像Windows的.exe文件，可以直接运行，如: {commands[0]} -help")
    
    # 并行获取所有命令的帮助信息
    # 通过运行 "命令名 -help" 来获取每个命令的详细帮助文档
    # 这就像在Windows中运行 "程序名 /?" 或 "程序名 --help" 一样
    command_help_data = fetch_command_helps(commands, commands_path, args.wm_project_dir)

    print(f"💾 保存命令列表文件: {output_dir / 'openfoam_commands.txt'}")
    with open(output_dir / "openfoam_commands.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(commands) + "\n")

    print(f"💾 保存命令帮助文件: {output_dir / 'openfoam_command_help.txt'}")
    with open(output_dir / "openfoam_command_help.txt", "w", encoding="utf-8") as f:
        for cmd, help_text in command_help_data.items():
            f.write(f"<command_begin><command>{cmd}</command><help_text>{help_text}</help_text></command_end>\n\n")

    print(f"🎉 教程解析完成！")
