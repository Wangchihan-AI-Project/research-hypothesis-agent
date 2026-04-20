"""
主入口文件
运行研究假设生成系统
"""
import sys
import os

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置工作目录为项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
# 明确指定.env文件路径
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path, encoding='utf-8')

from src.cli.main import main

if __name__ == '__main__':
    main()