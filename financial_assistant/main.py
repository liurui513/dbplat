# 【总入口】一键运行全流程或启动Web服务
import argparse
from database.db_loader import process_and_load, init_db
from frontend.app import run_frontend
from tests.test_integration import run_task2_tests, run_task3_tests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='web', choices=['init', 'parse', 'test2', 'test3', 'web'])
    parser.add_argument('--file', type=str, help='PDF file path for parsing')
    args = parser.parse_args()

    if args.mode == 'init':
        init_db()
    elif args.mode == 'parse':
        if args.file:
            process_and_load(args.file)
        else:
            print("请指定 --file 参数")
    elif args.mode == 'test2':
        run_task2_tests() # 处理附件4，生成 result_2.xlsx
    elif args.mode == 'test3':
        run_task3_tests() # 处理附件6，生成 result_3.xlsx
    elif args.mode == 'web':
        run_frontend()

if __name__ == "__main__":
    main()