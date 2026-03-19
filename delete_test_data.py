#!/usr/bin/env python3
import os
import shutil

test_data_path = r'e:\clawqwe\翻译脚本\rpg_translator\test_data'

if os.path.exists(test_data_path):
    try:
        shutil.rmtree(test_data_path)
        print(f"✅ 成功删除文件夹: {test_data_path}")
    except Exception as e:
        print(f"❌ 删除失败: {e}")
else:
    print(f"文件夹不存在: {test_data_path}")
